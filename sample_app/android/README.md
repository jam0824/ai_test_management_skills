# 老後資金シミュレーター(Android版)

Web版(`../web/retirement_simulator.html`)と同じ計算・同じ画面項目を、Kotlin + Jetpack Compose で作ったもの。
テスト活動のスキルが Android アプリでも回せるかを確かめるための題材。

- 計算はWeb版をそのまま移した。同じ入力なら結果の行もWeb版と1文字まで同じになる(数値の丸め方や表示の形もJavaScriptに合わせている)
- Web版と同じく、ネットワーク通信はしない(INTERNET 権限を宣言していない)
- 画面の回転では、入力と結果は消えない(ViewModel に持たせている)

## 動かすのに要るもの

- Android SDK(compileSdk 36)
- JDK 17 以上(Android Studio 付属の JDK でよい)
- 端末: Android 8.0(API 26)以上のエミュレータか実機

`local.properties` に SDK の場所を書く(Android Studio で開けば自動で作られる)。

```
sdk.dir=C\:/Users/<ユーザー名>/AppData/Local/Android/Sdk
```

## ビルドと起動

```powershell
$env:JAVA_HOME = "C:\Program Files\Android\Android Studio\jbr"
.\gradlew assembleDebug
adb install -r app\build\outputs\apk\debug\app-debug.apk
adb shell am start -n jp.sample.retirementsimulator/.MainActivity
```

## テスト

```powershell
.\gradlew testDebugUnitTest          # 計算のテスト(端末不要)
.\gradlew connectedDebugAndroidTest  # 画面のテスト(繋がっている全端末で動く)
```

- 画面のテストは、エミュレータ(Android 14)と実機の Pixel 8a(Android 17)で通ることを確かめた
- 端末が複数繋がっていると、`connectedDebugAndroidTest` は全部に入れて動かす。1台に絞るときは環境変数 `ANDROID_SERIAL` に端末のシリアルを入れる

## 画面の部品の id

UI Automator や Appium からは、次の名前が resource-id として見える(Compose の testTag を resource-id として出している)。
入力欄の id はWeb版の input の id と同じ。

| 部品 | id |
| --- | --- |
| 入力欄 | `startAge` `retirementAge` `pensionStartAge` `gapIncome` `salary` `monthlyPension` `initialCash` `initialInv` `expenseCurrent` `expenseGap` `expenseRetired` `investRate` `interest` `eventProb` |
| 給与変更設定の表示/非表示 | `toggleSalaryChanges` |
| 給与変更の枠 / 追加 | `salaryChanges` / `addSalaryChange` |
| 給与変更の1行(年齢・年収・削除) | `salaryChangeAge` `salaryChangeSalary` `salaryChangeDelete` |
| 開始 | `runBtn` |
| 結果の1行 | `outputLine` |
| 画面全体のスクロール | `screen` |

結果の行は画面に入った分しか作られない(LazyColumn)。先の行を見るときはスクロールが要る。
