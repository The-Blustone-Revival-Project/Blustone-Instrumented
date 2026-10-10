# Bounded native input helper

RapidTouch.java runs through Android `app_process` as shell, without changing
the APK or game data. It injects paired touchscreen down/up events at (550,800).
Count is limited to 1..12 and spacing to 50..1000 ms. The default is 8 taps,
60 ms apart. Injection failures abort after attempting release.

Before **each** invocation, verify that the instrumented package is foreground
and a fresh screenshot shows the active fishing hook or suitable battle HUD.
Do not run during menus, guides, loading, results or scene transitions. Inspect
the screen after each burst. An accepted event does not prove a game hit.

Build locally from the workspace in PowerShell (build outputs are ignored):

```powershell
$rapidJdk = "$PWD/tools/jdk/jdk-21.0.12.1+1"
$rapidApi = "$PWD/tools/android-sdk/platforms/android-33/android.jar"
New-Item -ItemType Directory analysis/rapid-touch/classes,analysis/rapid-touch/dex -Force
& "$rapidJdk/bin/javac.exe" -source 8 -target 8 -classpath $rapidApi -d analysis/rapid-touch/classes tools/RapidTouch.java
& "$rapidJdk/bin/java.exe" -cp tools/android-sdk/build-tools/37.0.0/lib/d8.jar com.android.tools.r8.D8 --lib $rapidApi --min-api 24 --output analysis/rapid-touch/dex analysis/rapid-touch/classes/RapidTouch.class
& "$rapidJdk/bin/jar.exe" --create --file analysis/rapid-touch/rapid-touch.jar -C analysis/rapid-touch/dex classes.dex
```

Copy to the BlueStacks shared folder, then only after the checks above:

```powershell
Copy-Item analysis/rapid-touch/rapid-touch.jar C:/ProgramData/BlueStacks_nxt/Engine/UserData/SharedFolder/RapidTouch.jar
& tools/android-sdk/platform-tools/adb.exe -s 127.0.0.1:5555 shell 'CLASSPATH=/mnt/windows/BstSharedFolder/RapidTouch.jar app_process /system/bin RapidTouch 8 60'
```

Compilation and guarded BlueStacks injection passed on 2026-10-07: 12 paired
events at 50 ms spacing completed in 557..561 ms; native fishing hit effects
rendered afterward. This does not prove all events passed the game's cooldown
or that a catch completed. There is no automatic foreground or phase guard.

Optional central-scene coordinates are now supported as the third/fourth args:
`RapidTouch 12 50 695 900`. X is limited400..750 and Y700..1050; supplying only
one coordinate refuses before injection. Default550/800 is preserved. The
Episode controller uses695/900 and can combine a visually verified preparation
screen's Begin action with native guarded inputs to avoid tool-call gaps.
The updated standalone JAR compiled/dexed and10nativebursts accepted120paired
inputs on2026-10-08. This helper is not an APK patch; no app reinstall/release.
