# visioncore
To address the limitations of XML-dependent mobile agents, We propose V-CORE, a vision-based collaborative framework that replaces XML-parsing with screenshot-based visual reasoning. By utilizing a local Vision Model, specifically LLAVA via Ollama, V-CORE performs on-device co-planning to identify task-relevant regions. Instead of uploading raw XML, the system shares a screenshot to the local LLM. The pipeline is shown below.


<img width="1212" height="490" alt="vcore_image" src="https://github.com/user-attachments/assets/64a07cb2-7560-4a58-a990-bf0a55f51838" />

# **Requirements**
1. Android Emulator
2. Java Development kit (JDK)
3. Android SDK

# **Python Environment**
We use Conda to manage our Python environment.
```bash
conda create -n CORE python=3.8
conda activate CORE
pip install -r requirements.txt
```

# Data Set Reference 
[DriodTask](https://github.com/MobileLLM/AutoDroid)

# LLM Configuration
**1.Cloud LLM**

We use OpenAI models for our Cloud LLM setup. To configure this, set your API key to the OPENAI_API_KEY environment variable.

**2.Local LLM**

To deploy a local model LLAVA, Follow instructions at [Ollama](https://ollama.com/).

# **ADB Keyboard**
ADB Keyboard is required for input automation.

1.Download ADBKeyBoard.apk.

2.Install the APK on your Android device or emulator:

```bash
adb install ADBKeyBoard.apk
```

3.Set ADB Keyboard as the default input method:

```bash
adb shell ime set com.android.adbkeyboard/.AdbIME
```

# **Usage**
The following command runs the automation pipeline on an Android app:
```bash
python start.py -pn "com.google.android.deskclock" -an "com.android.deskclock.DeskClock" -o "output" -task "add a new timer of 5:00" -keep_app -is_emulator
```

-pn: Package name of the app

-an: App name

-o: Output folder

-task: Natural language instruction

# **Important Notes**
1.Make sure your emulator is properly connected to your computer and in developer mode.

2.Ensure the target app is already installed before running the script. You can try open-source apps from [Simple Mobile Tools](https://github.com/SimpleMobileTools).
