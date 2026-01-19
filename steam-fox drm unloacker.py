import traceback

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, font
    from tkinterdnd2 import DND_FILES, TkinterDnD

    import requests
    import configparser
    import json
    import os
    import subprocess
    from sac_lib.get_file_version import GetFileVersion
    import shutil
    from time import sleep
    from sys import exit


    NEON_COLOR_PRIMARY = "#00FFFF"
    NEON_COLOR_SECONDARY = "#39FF14"
    BACKGROUND_COLOR = "#121212"
    FOREGROUND_COLOR = NEON_COLOR_PRIMARY
    DISABLED_COLOR = "#444444"
    BORDER_COLOR = "#008080"


    RETRY_DELAY = 15
    RETRY_MAX = 30
    HIGH_DLC_WARNING = 125

    folder_path = ""
    appID = 0
    gameSearchDone = False

    EXTS_TO_REPLACE = (".txt", ".ini", ".cfg")
    

    def OnTkinterError(exc, val, tb):
        print("\n[!!!] A Tkinter Python error occurred! (Simplified Log)")


    class SACRequest:
        def __init__(self, url:str, name:str = "Unnamed"):
            self.url = url
            self.tries = 0
            self.name = name
            self.DoRequest()

        def DoRequest(self):
            self.tries += 1
            req = requests.get(self.url, timeout=10)
            if not req.ok:
                if self.tries < int(config["Advanced"]["RetryMax"]):
                    # Do another try
                    update_logs("- " + self.name + " request failed, retrying...")
                    root.update()
                    sleep(int(config["Advanced"]["RetryDelay"]))
                    self.DoRequest()
                else:
                    update_logs("[!] Connection failed after max tries. Check Internet/Steam.")
                    raise Exception(f"SACRequest: Connection failed after {config['Advanced']['RetryMax']} tries")
            else:
                self.req = req

    def handle_folder_selection(event=None):
        global folder_path
        global last_selected_folder
        last_selected_folder = config["Preferences"].get("last_selected_folder", "")
        
        def reset_folder_selection_ui():
            selectedFolderLabel.config(text="")
            selectedFolderLabel.pack_forget()
            frameGame2.pack_forget()
            frameCrack2.pack_forget()

        if event:
            folder_path_temp = event.data.strip().strip("{}").replace("\\", "/")
        else:
            initial_dir = "/"
            if last_selected_folder != "" and os.path.isdir(last_selected_folder):
                initial_dir = last_selected_folder
            folder_path_temp = filedialog.askdirectory(initialdir=initial_dir)

        if os.path.isdir(folder_path_temp):
            folder_path = folder_path_temp
            last_selected_folder = os.path.dirname(folder_path)
            if not last_selected_folder:
                last_selected_folder = folder_path
            config["Preferences"]["last_selected_folder"] = last_selected_folder
            UpdateConfig()

            update_logs(f"\n✅ تم اختيار المجلد: {folder_path}")
            selectedFolderLabel.config(text=f"📂 المجلد المحدد:\n{folder_path}")
            selectedFolderLabel.pack(pady=5)
            frameGame2.pack()

            gameNameEntry.delete(0, tk.END)

            if gameSearchDone:
                frameCrack2.pack()
        else:
            update_logs("\n❌ لم يتم اختيار مجلد صالح")
            reset_folder_selection_ui()

    def update_logs(log_message):
        current_logs = logs_text.get("1.0", tk.END).strip()

        logs_text.config(state=tk.NORMAL)
        logs_text.delete("1.0", tk.END)

        new_content = current_logs
        if current_logs:
             new_content += "\n" + log_message
        else:
             new_content = log_message

        # Keep a max of 50 lines
        lines = new_content.split('\n')
        if len(lines) > 50:
            new_content = "\n".join(lines[-50:])

        logs_text.insert(tk.END, new_content)
        logs_text.yview_moveto(1.0)
        logs_text.see(tk.END)
        logs_text.config(state=tk.DISABLED)

    def search_game():
        searchGameButton.config(state=tk.DISABLED)
        frameCrack2.pack_forget()
        global gameSearchDone
        gameSearchDone = False

        gameFoundStatus.config(text=f"")
        selectFolderButton.config(state=tk.DISABLED)
        root.update()

        global appID
        appID = 0
        
        appID_input = gameNameEntry.get().strip()

        if appID_input == "":
            update_logs("\n[!] الرجاء إدخال AppID صالح")
            searchGameButton.config(state=tk.NORMAL)
            selectFolderButton.config(state=tk.NORMAL)
            return

        try:
            appID = int(appID_input)
        except ValueError:
            update_logs("\n[!] يجب أن يكون AppID رقماً فقط.")
            searchGameButton.config(state=tk.NORMAL)
            selectFolderButton.config(state=tk.NORMAL)
            return
        
        if appID != 0 and RetrieveGame():
            gameSearchDone = True
            frameCrack2.pack()
            searchGameButton.config(state=tk.NORMAL)
            selectFolderButton.config(state=tk.NORMAL)
        else:
            searchGameButton.config(state=tk.NORMAL)
            selectFolderButton.config(state=tk.NORMAL)

    def RetrieveAppName(appID: int) -> str:
        try:
            req = SACRequest("https://store.steampowered.com/api/appdetails?appids=" + str(appID) + "&filters=basic", "RetrieveAppName").req
        except Exception:
            return "error"

        data = req.json()
        data = data[str(appID)]
        if (not "data" in data) or (not "name" in data["data"]):
            return "error"
        return data["data"]["name"]

    def RetrieveGame() -> bool:
        global appID
        global gameName
        global dlcIDs
        global dlcNames

        dlcIDs = []
        dlcNames = []

        update_logs("\n[1/2] 🔍 جلب معلومات اللعبة من Steam...")
        gameFoundStatus.config(text=f"[1/2] جاري جلب المعلومات...")
        root.update()
        
        try:
            req = SACRequest("https://store.steampowered.com/api/appdetails?appids=" + str(appID) + "&filters=basic", "RetrieveGame").req
        except Exception:
            gameFoundStatus.config(text=f"❌ حدث خطأ في الاتصال")
            return False
        data = req.json()
        data = data[str(appID)]
        if not data["success"]:
            update_logs(f"\n[!] AppID {appID} غير موجود.")
            gameFoundStatus.config(text=f"❌ AppID {appID} غير موجود.")
            appID = 0
            return False
        
        # تم تبسيط التحقق
        if config["Advanced"]["BypassGameVerification"] != "1" and "data" in data and "type" in data["data"] and data["data"]["type"] != "game":
             update_logs(f"\n[!] AppID {appID} ليس لعبة.")
             gameFoundStatus.config(text=f"⚠️ AppID {appID} ليس لعبة.")
             appID = 0
             return False


        gameName = data["data"]["name"]
        appID = data["data"]["steam_appid"]
        update_logs(f"✅ تم العثور على اللعبة! الاسم: {gameName} - AppID: {appID}")

        update_logs("\n[2/2] 📦 جلب محتويات DLC...")
        gameFoundStatus.config(text=f"[2/2] جاري جلب محتويات DLC...")
        root.update()



        try:
            req2 = SACRequest("https://store.steampowered.com/dlc/" + str(appID) +"/random/ajaxgetfilteredrecommendations/?query&count=10000", "RetrieveDLC").req
        except Exception:
            gameFoundStatus.config(text=f"❌ حدث خطأ في الاتصال")
            return False
        data2 = req2.json()
        if not data2["success"]:
            update_logs("[!] فشل طلب جلب محتويات DLC!")
            gameFoundStatus.config(text=f"❌ فشل جلب محتويات DLC!")
            appID = 0
            return False

        if data2["total_count"] == 0:
            update_logs("- لم يتم العثور على محتويات DLC لهذه اللعبة!")
        else:
            if data2["total_count"] >= HIGH_DLC_WARNING:
                update_logs(f"تحذير: تحتوي اللعبة على أكثر من {HIGH_DLC_WARNING} محتوى إضافي.")

            resultsIndex = 0

            i = -1
            while i + 1 < data2["total_count"]:
                i += 1

                resultsStr = ""
                resultsIndex = data2["results_html"].find("data-ds-appid=\"", resultsIndex)
                resultsIndex += len("data-ds-appid=\"")

                if resultsIndex >= len(data2["results_html"]):
                    break

                while data2["results_html"][resultsIndex] != "\"":
                    resultsStr += data2["results_html"][resultsIndex]
                    resultsIndex += 1

                dlcID = int(resultsStr)
                if dlcID in dlcIDs:
                    i -= 1
                    continue
                dlcIDs.append(int(resultsStr))

                # Retrieve DLC name
                appName = RetrieveAppName(dlcIDs[i])
                if appName == "error":
                    update_logs(f"[!] خطأ! لم يتم العثور على اسم لـ AppID {dlcIDs[i]}")
                    gameFoundStatus.config(text=f"❌ خطأ! لم يتم العثور على اسم لـ AppID {dlcIDs[i]}")
                    appID = 0
                    return False
                dlcNames.append(appName)
                update_logs("- تم العثور على DLC " + str(i+1) + "/" + str(data2["total_count"]) + ": " + appName + " (" + str(dlcIDs[i]) + ")")
                gameFoundStatus.config(text=f"[2/2] جلب محتويات DLC... ({i+1}/{data2['total_count']})")
                root.update()

        update_logs(f"✅ انتهى جلب جميع التفاصيل حول اللعبة {gameName} (appID: {appID})")
        gameFoundStatus.config(text=f"✅ تم جلب جميع التفاصيل لـ {gameName}!")
        return True

    def CrackGame():
        global appID

        selectFolderButton.config(state=tk.DISABLED)
        searchGameButton.config(state=tk.DISABLED)
        selectCrackButton.config(state=tk.DISABLED)
        crackGameButton.config(state=tk.DISABLED)

        update_logs("\n🛠️ جاري البحث عن ملفات Steam API DLL وتطبيق الكراك...")
        cracked = False

        if config["Crack"]["SelectedCrack"][:3] == "dlc" and len(dlcIDs) == 0:
            update_logs("-----\n⚠️ لا تتوفر محتويات DLC، وقد اخترت كراكاً خاصاً بمحتويات DLC فقط. جاري إلغاء عملية التكريك.")
            EndCrack()
            return

        configDir = os.path.join(os.getcwd(), "sac_emu\\" + config["Crack"]["SelectedCrack"])
        try:
            config.read(configDir + "\\config_override.ini")
        except Exception:
            pass

        configDir = os.path.join(configDir, "files")

        steamlessOptions = config["Developer"].get("SteamlessOptions", "") + " " if "Developer" in config and "SteamlessOptions" in config["Developer"] else ""

        root.update()

        dllLocations = []
        for root_dir, dirs, files in os.walk(folder_path):
            apiFile = ""

            # Use Steamless if configured
            if config["Preferences"]["Steamless"] == "1" and crackListSteamless.get(config["Crack"]["SelectedCrack"], False):
                for fileName in files:
                    if not fileName.endswith(".exe"):
                        continue
                    update_logs(f"- محاولة تشغيل Steamless على {fileName}")
                    root.update()
                    
                    fileLocation = root_dir + "/" + fileName

                    shutil.move(fileLocation, fileName)
                    subprocess.call("Steamless_CLI\\Steamless.CLI.exe " + steamlessOptions + "\"" + fileName + "\"", shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)

                    if not os.path.isfile(fileName + ".unpacked.exe"):
                        update_logs("- لم يتمكن Steamless من العمل على " + fileName)
                        shutil.move(fileName, fileLocation)
                        root.update()
                        continue

                    update_logs(f"✓ تمت إزالة حماية Steam Stub DRM من {fileName}")
                    

                    if config["FileNames"]["GameEXE"] != "":
                        shutil.move(fileName, fileLocation + config["FileNames"]["GameEXE"])
                    else:
                        os.remove(fileName)
                    shutil.move(fileName + ".unpacked.exe", fileLocation)
                    root.update()



            if "steam_api.dll" in files:
                if config["FileNames"]["SteamAPI"] in files:

                    update_logs("[!] steam_api.dll مكرك مسبقاً! جاري الكتابة فوقه. تمت استعادة النسخة الاحتياطية.")
                    os.remove(root_dir + "/steam_api.dll")
                    shutil.move(root_dir + "/" + config["FileNames"]["SteamAPI"], root_dir + "/steam_api.dll")

                apiFile = root_dir + "/steam_api.dll"
                try:
                    apiFileVersion = GetFileVersion(apiFile)
                except Exception:
                    update_logs("[!] steam_api.dll: تعذر جلب إصدار الملف! تم الإلغاء...")
                    EndCrack()
                    return

                update_logs(f"✓ تم العثور على steam_api.dll في {root_dir}")

            if "steam_api64.dll" in files:
                if config["FileNames"]["SteamAPI64"] in files:

                    update_logs("[!] steam_api64.dll مكرك مسبقاً! جاري الكتابة فوقه. تمت استعادة النسخة الاحتياطية.")
                    os.remove(root_dir + "/steam_api64.dll")
                    shutil.move(root_dir + "/" + config["FileNames"]["SteamAPI64"], root_dir + "/steam_api64.dll")

                apiFile = root_dir + "/steam_api64.dll"
                try:
                    apiFileVersion = GetFileVersion(apiFile)
                except Exception:
                    update_logs("[!] steam_api64.dll: تعذر جلب إصدار الملف! تم الإلغاء...")
                    EndCrack()
                    return

                update_logs(f"✓ تم العثور على steam_api64.dll في {root_dir}")

            if apiFile != "":
                if root_dir not in dllLocations:
                    dllLocations.append(root_dir)

                cracked = True
                root.update()


        for dllCurrentLocation in dllLocations:
            for root_dir, dirs, files in os.walk(configDir):
                relativeRootDir = root_dir[len(configDir) + 1:]
                dllAbsoluteRelativeLocation = os.path.join(dllCurrentLocation, relativeRootDir)

                if len(relativeRootDir) > 0:
                    relativeRootDir += "\\"

                for dir in dirs:
                    if not os.path.isdir(os.path.join(dllAbsoluteRelativeLocation, dir)):
                        os.mkdir(os.path.join(dllAbsoluteRelativeLocation, dir))
                        update_logs("تم إنشاء دليل جديد " + relativeRootDir + dir)
                        root.update()

                for fileName in files:
                    root.update()
                    if os.path.isfile(os.path.join(dllAbsoluteRelativeLocation, fileName)):
                        newName = fileName + config["FileNames"]["BakSuffix"]
                        if fileName == "steam_api.dll" or fileName == "steam_api64.dll":
                            if config["Preferences"]["CrackOption"] != "0":
                                update_logs("تجاهل " + relativeRootDir + fileName + " بسبب إعداد طريقة الكراك")
                                continue

                            if fileName == "steam_api.dll":
                                newName = config["FileNames"]["SteamAPI"]
                            else:
                                newName = config["FileNames"]["SteamAPI64"]

                        if newName == "":
                            os.remove(os.path.join(dllAbsoluteRelativeLocation, fileName))
                            update_logs("تمت إزالة الملف القديم " + relativeRootDir + fileName)
                        elif os.path.isfile(os.path.join(dllAbsoluteRelativeLocation, newName)):
                            update_logs("[!] النسخة الاحتياطية للملف " + relativeRootDir + fileName + " موجودة بالفعل! تم حذف الملف القديم.")
                            os.remove(os.path.join(dllAbsoluteRelativeLocation, fileName))
                        else:
                            shutil.move(os.path.join(dllAbsoluteRelativeLocation, fileName), os.path.join(dllAbsoluteRelativeLocation, newName))
                            update_logs("تم حفظ نسخة احتياطية من الملف القديم " + relativeRootDir + fileName + " -> " + newName)
                    elif fileName == "steam_api.dll" or fileName == "steam_api64.dll":
                        continue

                    shutil.copyfile(os.path.join(root_dir, fileName), os.path.join(dllAbsoluteRelativeLocation, fileName))

                    if any(fileName.endswith(extension) for extension in EXTS_TO_REPLACE):
                        with open(os.path.join(dllAbsoluteRelativeLocation, fileName), "r", encoding="utf-8") as file:
                            fileContent = file.read()


                        fileContent = fileContent.replace("SAC_AppID", str(appID))
                        fileContent = fileContent.replace("SAC_APIVersion", apiFileVersion)
                        buffer = ""
                        for i in range(len(dlcIDs)):
                            buffer += str(dlcIDs[i]) + " = " + dlcNames[i] + "\n"
                        fileContent = fileContent.replace("SAC_DLC", buffer)
                        buffer = ""
                        for i in range(len(dlcIDs)):
                            buffer += str(dlcIDs[i]) + "=" + dlcNames[i] + "\n"
                        fileContent = fileContent.replace("SAC_NoSpaceDLC", buffer)

                        with open(os.path.join(dllAbsoluteRelativeLocation, fileName), "w", encoding="utf-8") as file:
                            file.write(fileContent)

                    update_logs("تم إنشاء ملف جديد " + relativeRootDir + fileName)


        update_logs("\n-----\n🎉 انتهى تكريك اللعبة بنجاح!")
        if not cracked:
            update_logs("[!] لم يتم العثور على أي Steam API DLL في اللعبة!")
        else:
            update_logs("تم تكريك اللعبة بنجاح!")

        EndCrack()

    def EndCrack():
        ReloadConfig()
        selectFolderButton.config(state=tk.NORMAL)
        searchGameButton.config(state=tk.NORMAL)
        selectCrackButton.config(state=tk.NORMAL)
        crackGameButton.config(state=tk.NORMAL)

    # ----- Crack List Functions -----

    crackList = {
        "game_ali213": ["stm.afandi", "كراك شامل للعبة والـ DLC، بسيط وموثوق."],
        "game_goldberg": ["Goldberg (Game)", "كراك مخصص لمحاكاة Steam للميزات الأساسية للعبة."],
        "dlc_creamapi": ["CreamAPI (DLC)", "كراك لتفعيل محتويات DLC بشكل أساسي."]
    }

    crackListSteamless = {
        "game_ali213": True,
        "game_goldberg": True,
        "dlc_creamapi": False
    }

    def DisplayCrackList():
        top = tk.Toplevel(root)
        top.title(f"steam fox broker - طرق الكراك")
        top.resizable(False, False)
        top.configure(bg=BACKGROUND_COLOR)
        
        ttk.Label(top, text= "🔨 قائمة الكراكات", font=("Arial", 14, "bold"), background=BACKGROUND_COLOR, foreground=FOREGROUND_COLOR).pack(padx=200, pady=(10,10), anchor="center")

        ttk.Button(top, text="إعادة ضبط الافتراضي", command=ResetCrackListButton).pack(pady=(0,10), anchor="center")

        ttk.Label(top, text="الكراك المختار:", font=("Arial", 12, "bold"), background=BACKGROUND_COLOR, foreground=FOREGROUND_COLOR).pack(padx=(6, 0), pady=(10,0), anchor="w")
        settings_frame1 = ttk.Frame(top, style='Neon.TFrame')
        settings_frame1.pack(padx=(15, 0), pady=(0, 0), anchor="w")

        global SelectedCrack_var
        SelectedCrack_var = tk.StringVar()
        SelectedCrack_var.set(config["Crack"]["SelectedCrack"])
        rowNum = 0
        for k, v in crackList.items():
            ttk.Radiobutton(settings_frame1, text=v[0], variable=SelectedCrack_var, value=k, command=lambda: UpdateSelectedCrack()).grid(row=rowNum, column=0, sticky="w")
            rowNum += 1
            tk.Label(settings_frame1, text=v[1], font=("Arial", 8), fg=NEON_COLOR_SECONDARY, bg=BACKGROUND_COLOR, wraplength=700, justify="left").grid(row=rowNum, column=0, sticky="w", ipadx=20)
            rowNum += 1

        tk.Label(top, text="", bg=BACKGROUND_COLOR).pack()

        top.grab_set()

    def UpdateSelectedCrack():
        value = SelectedCrack_var.get()
        UpdateConfigKey("Crack", "SelectedCrack", value)
        UpdateSelectedCrackDisplay()

    def UpdateSelectedCrackDisplay():
        selectCrackButton.config(text=crackList[config["Crack"]["SelectedCrack"]][0])

    def ResetCrackListButton():
        ResetConfig(2)
        SelectedCrack_var.set(config["Crack"]["SelectedCrack"])
        UpdateSelectedCrackDisplay()



    def UpdateConfig():
        with open("config.ini", "w", encoding="utf-8") as configFile:
            config.write(configFile)

    def UpdateConfigKey(section: str, key: str, value: str):
        config[section][key] = value
        UpdateConfig()

    def ResetConfig(resetLevel = 0, customConfig=None):

        if customConfig:
            currentConfig = customConfig
        else:
            currentConfig = config

        if resetLevel == 0 or resetLevel == 1:
            currentConfig["Preferences"] = {}
            currentConfig["Preferences"]["UpdateOption"] = "0"
            currentConfig["Preferences"]["CrackOption"] = "0"
            currentConfig["Preferences"]["Steamless"] = "1"
            currentConfig["Preferences"]["last_selected_folder"] = ""

            currentConfig["FileNames"] = {}
            currentConfig["FileNames"]["GameEXE"] = ".bak"
            currentConfig["FileNames"]["BakSuffix"] = ".bak"
            currentConfig["FileNames"]["SteamAPI"] = "steam_api.dll.bak"
            currentConfig["FileNames"]["SteamAPI64"] = "steam_api64.dll.bak"

            currentConfig["Advanced"] = {}
            currentConfig["Advanced"]["RetryDelay"] = str(RETRY_DELAY)
            currentConfig["Advanced"]["RetryMax"] = str(RETRY_MAX)
            currentConfig["Advanced"]["BypassGameVerification"] = "0"
            

            if "Developer" not in currentConfig:
                currentConfig["Developer"] = {}
                currentConfig["Developer"]["RetrieveDLCOption"] = "0" 
                currentConfig["Developer"]["SteamlessOptions"] = ""

        if resetLevel == 0 or resetLevel == 2:
            currentConfig["Crack"] = {}
            currentConfig["Crack"]["SelectedCrack"] = "game_ali213"

        if not customConfig:
            UpdateConfig()

    def FillConfig(currentConfig, configDefault):
        changed = False
        for k, v in configDefault.items():
            if k not in currentConfig:
                currentConfig[k] = v
                changed = True
            if type(v) == configparser.SectionProxy:
                if FillConfig(currentConfig[k], v):
                    changed = True

        return changed

    def ReloadConfig():
        global config
        config = configparser.ConfigParser()

        if config.read("config.ini") == []:
            ResetConfig()
        else:
            configDefault = configparser.ConfigParser()
            ResetConfig(0, configDefault)

            changed = FillConfig(config, configDefault)
            if changed:
                UpdateConfig()

    ReloadConfig()


    root = TkinterDnD.Tk()
    root.configure(bg=BACKGROUND_COLOR)
    root.resizable(True, True)
    root.title(f"steam fox broker")
    root.drop_target_register(DND_FILES)
    root.dnd_bind("<<Drop>>", lambda event: handle_folder_selection(event=event))

    DEFAULT_FONT = font.nametofont('TkTextFont')
    FONT2 = ("Arial", 18, "bold")
    FONT3 = ("Arial", 12, "bold")
    FONT4 = ("Arial", 8)
    FONT_APP_ENTRY = ("Arial", 10)

    style = ttk.Style()
    
    style.theme_create("neon_theme_simple", parent="alt", settings={
        "TFrame": {"configure": {"background": BACKGROUND_COLOR}},
        "TLabel": {"configure": {"background": BACKGROUND_COLOR, "foreground": FOREGROUND_COLOR, "font": DEFAULT_FONT, "padding": 6}},
        "TButton": {"configure": {"background": BACKGROUND_COLOR, "foreground": FOREGROUND_COLOR, "padding": [15, 8]}},
        "TRadiobutton": {"configure": {"background": BACKGROUND_COLOR, "foreground": FOREGROUND_COLOR, "padding": 6}},
        "TSeparator": {"configure": {"background": BORDER_COLOR}},
        "Vertical.TScrollbar": {"configure": {"background": DISABLED_COLOR}}
    })
    style.theme_use("neon_theme_simple")

    main_frame = tk.Frame(root, bg=BACKGROUND_COLOR)
    main_frame.pack(fill="both", expand=True, padx=20, pady=20)
    
    right_frame = tk.Frame(main_frame, bg=BACKGROUND_COLOR)
    right_frame.pack(side="right", fill="y", padx=(10, 0))

    left_frame = tk.Frame(main_frame, bg=BACKGROUND_COLOR)
    left_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))


    header_frame = tk.Frame(right_frame, bg=BACKGROUND_COLOR)
    header_frame.pack(pady=(0, 0), anchor="center")
    tk.Label(header_frame, text=f"✨ steam fox broker ✨", font=FONT2, fg=FOREGROUND_COLOR, bg=BACKGROUND_COLOR).pack(pady=(10, 0))
    ttk.Label(header_frame, text="steam fox dlc unloacker by seif afandi and abdalrhman", style='TLabel', foreground=NEON_COLOR_SECONDARY, font=FONT4, padding=0).pack(pady=(0, 20))

    ttk.Separator(right_frame, orient='horizontal').pack(fill="x", padx=10, pady=(10, 20))


    tk.Label(right_frame, text="الخطوة 1: حدد مجلد تثبيت لعبتك:", fg=NEON_COLOR_SECONDARY, bg=BACKGROUND_COLOR).pack(pady=(5, 5), anchor="center")
    selectFolderButton = ttk.Button(right_frame, text="📂 اختيار مجلد اللعبة", command=lambda: handle_folder_selection())
    selectFolderButton.pack(pady=(0, 10))

    selectedFolderFrame = tk.Frame(right_frame, bg=BACKGROUND_COLOR)
    selectedFolderFrame.pack(padx=20)
    selectedFolderLabel = tk.Label(selectedFolderFrame, text="", wraplength=700, justify="center", fg=NEON_COLOR_PRIMARY, bg=BACKGROUND_COLOR)
    selectedFolderLabel.pack()
    selectedFolderLabel.pack_forget()

    frameGame = ttk.Frame(right_frame)
    frameGame.pack(pady=(15, 0), anchor="center")

    frameGame2 = ttk.Frame(frameGame)
    frameGame2.pack()
    
    ttk.Separator(frameGame2, orient='horizontal').pack(fill="x", padx=50, pady=(15, 0))
    
    ttk.Label(frameGame2, text="الخطوة 2: أدخل **AppID** اللعبة المطلوبة:", font=FONT3).pack(pady=(15, 5), anchor="center")

    frame4 = ttk.Frame(frameGame2)
    frame4.pack(pady=(5, 10), anchor="center")
    
    gameNameEntry = tk.Entry(frame4, width=35, font=FONT_APP_ENTRY, bg=BACKGROUND_COLOR, fg=NEON_COLOR_SECONDARY, insertbackground=NEON_COLOR_PRIMARY, bd=1, relief="solid")
    gameNameEntry.grid(row=0, column=0, ipady=5)
    
    searchGameButton = ttk.Button(frame4, text="🔎 بحث AppID", command=search_game)
    searchGameButton.grid(row=0, column=1, padx=(10, 0))

    gameFoundStatus = ttk.Label(frameGame2, text="")
    gameFoundStatus.pack(pady=(5, 10), anchor="center")

    frameGame2.pack_forget()

    frameCrack = ttk.Frame(right_frame)
    frameCrack.pack(pady=(15, 0), anchor="center")
    
    frameCrack2 = ttk.Frame(frameCrack)
    frameCrack2.pack()
    
    ttk.Separator(frameCrack2, orient='horizontal').pack(fill="x", padx=0, pady=(0, 15))
    
    ttk.Label(frameCrack2, text="الخطوة 3: اختر الكراك وقم بالتطبيق:", font=FONT3).pack(pady=(0, 5), anchor="center")
    
    selectedCrackFrame = ttk.Frame(frameCrack2)
    selectedCrackFrame.pack()
    
    tk.Label(selectedCrackFrame, text="🔨 الكراك المختار:", fg=NEON_COLOR_SECONDARY, bg=BACKGROUND_COLOR).grid(row=0, column=0)
    selectCrackButton = ttk.Button(selectedCrackFrame, text="None", command=DisplayCrackList)
    selectCrackButton.grid(row=0, column=1, padx=(10, 0))
    UpdateSelectedCrackDisplay()
    
    crackGameButton = ttk.Button(frameCrack2, text="🚀 بدء عملية التكريك", command=CrackGame)
    crackGameButton.pack(pady=(15, 10))

    frameCrack2.pack_forget()
    
 
    ttk.Label(left_frame, text="📜 سجلات العمليات:").pack(pady=(0, 0), anchor="center")

    logs_text = tk.Text(left_frame, height=35, width=60,
                        bg=BACKGROUND_COLOR, fg=NEON_COLOR_PRIMARY, 
                        insertbackground=NEON_COLOR_SECONDARY, bd=0, 
                        relief="flat", 
                        highlightbackground=BORDER_COLOR,
                        highlightcolor=BORDER_COLOR,
                        highlightthickness=3)
    logs_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    
    logs_scrollbar = ttk.Scrollbar(left_frame, command=logs_text.yview)
    logs_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    logs_text.config(yscrollcommand=logs_scrollbar.set)
    
    text = f"steam fox broker" 
    buf = "-" * len(text)
    logs_text.insert("1.0", f"[{buf}]\n[ {text} ]\n[{buf}]\n\n👋 أهلاً بك في steam fox broker! يرجى البدء باختيار مجلد لعبتك.\n")
    logs_text.config(state=tk.DISABLED)


    root.report_callback_exception = OnTkinterError


    if os.path.isfile("steam_auto_cracker_gui_autoupdater.exe"):
        try:
            os.remove("steam_auto_cracker_gui_autoupdater.exe")
        except Exception:
            pass


    root.mainloop()

except Exception:
    print("\n[!!!] A Python error occurred! (Simplified Log)")