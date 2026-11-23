# テスト結果(E2E自動テスト)

E2E自動テストスクリプトの実行結果を、ローレベルテストケースのidで対応づけたもの。

1回目(2026-11-23 10:42〜12:50、`証跡/E2E/report.json`)の途中、12:30ごろからエミュレータが不調になり(システムの Watchdog、Pixel Launcher の ANR、アプリの ANR。`証跡/環境/`)、29件がスクリプトの途中で止まった。エミュレータを再起動して、その29件を `証跡/E2E_再実行/` に流し直し(12:59〜14:37)、そこでもアプリの ANR などで止まった5件を `証跡/E2E_再実行2/` に流し直した(14:40〜15:07)。この表は、それぞれのidの最後の実行の結果を1つにした `証跡/E2E_統合/report.json` から作った。前の実行の結果と証跡は消していない。

| ローレベルテストケースID | 実施方法 | 結果 | 証跡 | 欠陥レポートID | メモ |
|---|---|---|---|---|---|
| LTC-001 | E2E自動テスト | Fail | 証跡/LTC-001_1_end.png<br>証跡/LTC-001_2_end_dump.xml<br>証跡/LTC-001_3_判定.txt<br>証跡/E2E_統合/report.json | BUG-005 | 1回目(証跡/E2E)はエミュレータの不調(Pixel Launcher の ANR とシステムの Watchdog、アプリの ANR)でスクリプトが途中で止まったので、エミュレータを再起動して流し直した結果(証跡/E2E_再実行)。原因: テスト対象の不具合。現役時生活費の初期値が 155600(期待値 156000)。ほかの13項目は期待値どおり |
| LTC-002 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  | 1回目(証跡/E2E)はエミュレータの不調(Pixel Launcher の ANR とシステムの Watchdog、アプリの ANR)でスクリプトが途中で止まったので、エミュレータを再起動して流し直した結果(証跡/E2E_再実行)。証跡は 証跡/E2E_再実行/evidence/LTC-002/ |
| LTC-003 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  | 1回目(証跡/E2E)はエミュレータの不調(Pixel Launcher の ANR とシステムの Watchdog、アプリの ANR)でスクリプトが途中で止まったので、エミュレータを再起動して流し直した結果(証跡/E2E_再実行)。証跡は 証跡/E2E_再実行/evidence/LTC-003/ |
| LTC-004 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  |  |
| LTC-005 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  |  |
| LTC-006 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  |  |
| LTC-007 | E2E自動テスト | Fail | 証跡/LTC-007_1_end.png<br>証跡/LTC-007_2_end_dump.xml<br>証跡/LTC-007_3_run1_総資産_取り崩しと資金切れ_dump_first.xml<br>証跡/LTC-007_4_run1_総資産_取り崩しと資金切れ_dump_last.xml<br>証跡/LTC-007_5_run1_総資産_取り崩しと資金切れ_lines.txt<br>証跡/LTC-007_6_判定.txt<br>証跡/E2E_統合/report.json | BUG-006 | 原因: テスト対象の不具合。72/552 行で総資産が現金 + 投資と1円ずれる(すべて投資がマイナスの行)。丸め方は Q-022 待ち |
| LTC-008 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  |  |
| LTC-009 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  |  |
| LTC-010 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  |  |
| LTC-011 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  |  |
| LTC-012 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  |  |
| LTC-013 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  |  |
| LTC-014 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  |  |
| LTC-015 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  |  |
| LTC-016 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  |  |
| LTC-017 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  | 1回目(証跡/E2E)と2回目(証跡/E2E_再実行)はエミュレータの不調(アプリの ANR など)でスクリプトが途中で止まったので、3回目(証跡/E2E_再実行2)の結果。証跡は 証跡/E2E_再実行2/evidence/LTC-017/ |
| LTC-018 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  |  |
| LTC-019 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  |  |
| LTC-020 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  |  |
| LTC-021 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  |  |
| LTC-022 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  |  |
| LTC-023 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  |  |
| LTC-024 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  |  |
| LTC-025 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  |  |
| LTC-026 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  |  |
| LTC-027 | E2E自動テスト | Fail | 証跡/LTC-027_1_end.png<br>証跡/LTC-027_2_end_dump.xml<br>証跡/LTC-027_3_共有_run10_年収1000000_lines.txt<br>証跡/LTC-027_4_共有_run11_年収1500000_lines.txt<br>証跡/LTC-027_5_共有_run12_年収2000000_lines.txt<br>証跡/LTC-027_6_共有_run13_年収3000000_lines.txt<br>証跡/LTC-027_7_共有_run14_年収4000000_lines.txt<br>証跡/LTC-027_8_共有_run15_年収5000000_lines.txt<br>証跡/LTC-027_9_共有_run16_年収6000000_lines.txt<br>証跡/LTC-027_10_共有_run17_年収7000000_lines.txt<br>証跡/LTC-027_11_共有_run18_年収8000000_lines.txt<br>証跡/LTC-027_12_共有_run19_年収10000000_lines.txt<br>証跡/LTC-027_13_共有_run1_年収1_lines.txt<br>証跡/LTC-027_14_共有_run20_年収12000000_lines.txt<br>証跡/LTC-027_15_共有_run21_年収15000000_lines.txt<br>証跡/LTC-027_16_共有_run22_年収20000000_lines.txt<br>証跡/LTC-027_17_共有_run23_年収30000000_lines.txt<br>証跡/LTC-027_18_共有_run24_年収50000000_lines.txt<br>証跡/LTC-027_19_共有_run25_年収100000000_lines.txt<br>証跡/LTC-027_20_共有_run2_年収100000_lines.txt<br>証跡/LTC-027_21_共有_run3_年収300000_lines.txt<br>証跡/LTC-027_22_共有_run4_年収470000_lines.txt<br>証跡/LTC-027_23_共有_run5_年収500000_lines.txt<br>証跡/LTC-027_24_共有_run6_年収600000_lines.txt<br>証跡/LTC-027_25_共有_run7_年収700000_lines.txt<br>証跡/LTC-027_26_共有_run8_年収800000_lines.txt<br>証跡/LTC-027_27_共有_run9_年収900000_lines.txt<br>証跡/LTC-027_28_判定.txt<br>証跡/E2E_統合/report.json |  | 原因: ローレベルテストケースの誤り(テストウェア)。年収1円の段の給与収入は表示で ¥0 に丸められ、割合が 0 になる。許容の項 1 ÷ (多い段の年収÷12) は多い段の丸めしか見ておらず、少ない段(年収1円)の丸め(最大 12)を許容していない。ほかの23組は成り立った。給与収入は 0.86 × 年収÷12 などで額面ではなく手取りと確認(Q-021 の前提は成り立つ)。テスト実装に報告 |
| LTC-028 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  |  |
| LTC-029 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  |  |
| LTC-030 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  |  |
| LTC-031 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  |  |
| LTC-032 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  |  |
| LTC-033 | E2E自動テスト | Fail | 証跡/LTC-033_1_end.png<br>証跡/LTC-033_2_end_dump.xml<br>証跡/LTC-033_3_run1_利回り0_dump_first.xml<br>証跡/LTC-033_4_run1_利回り0_dump_last.xml<br>証跡/LTC-033_5_run1_利回り0_lines.txt<br>証跡/LTC-033_6_run2_利回り1_dump_first.xml<br>証跡/LTC-033_7_run2_利回り1_dump_last.xml<br>証跡/LTC-033_8_run2_利回り1_lines.txt<br>証跡/LTC-033_9_run3_利回り4_dump_first.xml<br>証跡/LTC-033_10_run3_利回り4_dump_last.xml<br>証跡/LTC-033_11_run3_利回り4_lines.txt<br>証跡/LTC-033_12_run4_利回り10_dump_first.xml<br>証跡/LTC-033_13_run4_利回り10_dump_last.xml<br>証跡/LTC-033_14_run4_利回り10_lines.txt<br>証跡/LTC-033_15_run5_利回り100_dump_first.xml<br>証跡/LTC-033_16_run5_利回り100_dump_last.xml<br>証跡/LTC-033_17_run5_利回り100_lines.txt<br>証跡/LTC-033_18_判定.txt<br>証跡/E2E_統合/report.json | BUG-002 | 原因: テスト対象の不具合。投資残高がマイナスになり(BUG-002)、マイナスに利回りが掛かって利回りの高いほうが投資が少なくなる |
| LTC-034 | E2E自動テスト | Fail | 証跡/LTC-034_1_end.png<br>証跡/LTC-034_2_end_dump.xml<br>証跡/LTC-034_3_run1_投資率0_dump_first.xml<br>証跡/LTC-034_4_run1_投資率0_dump_last.xml<br>証跡/LTC-034_5_run1_投資率0_lines.txt<br>証跡/LTC-034_6_run2_投資率20_dump_first.xml<br>証跡/LTC-034_7_run2_投資率20_dump_last.xml<br>証跡/LTC-034_8_run2_投資率20_lines.txt<br>証跡/LTC-034_9_run3_投資率50_dump_first.xml<br>証跡/LTC-034_10_run3_投資率50_dump_last.xml<br>証跡/LTC-034_11_run3_投資率50_lines.txt<br>証跡/LTC-034_12_run4_投資率100_dump_first.xml<br>証跡/LTC-034_13_run4_投資率100_dump_last.xml<br>証跡/LTC-034_14_run4_投資率100_lines.txt<br>証跡/LTC-034_15_判定.txt<br>証跡/E2E_統合/report.json | BUG-001、BUG-002 | 原因: テスト対象の不具合。投資率を上げると現役中も毎月補填が起き、補填のたびに20%の「税金」が投資から引かれる(BUG-001)。投資率0→20 の組は投資がマイナスになった行(BUG-002) |
| LTC-035 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  |  |
| LTC-036 | E2E自動テスト | Fail | 証跡/LTC-036_1_end.png<br>証跡/LTC-036_2_end_dump.xml<br>証跡/LTC-036_3_run1_総資産の増減_dump_first.xml<br>証跡/LTC-036_4_run1_総資産の増減_dump_last.xml<br>証跡/LTC-036_5_run1_総資産の増減_lines.txt<br>証跡/LTC-036_6_判定.txt<br>証跡/E2E_統合/report.json | BUG-001 | 原因: テスト対象の不具合。補填した月に、補填額の20%(税金)だけ総資産が収入 − 生活費より多く減る(181/246 行) | (総資産 − 前の行の総資産) − (収入 − 生活費)\ | < 4円: 181/246 件で成り立たない(例: 60歳7月 総資産 22387500→22233500 収入 50000 生活費 200000; 6 |
| LTC-037 | E2E自動テスト | Fail | 証跡/LTC-037_1_end.png<br>証跡/LTC-037_2_end_dump.xml<br>証跡/LTC-037_3_run1_現金不足_dump_first.xml<br>証跡/LTC-037_4_run1_現金不足_dump_last.xml<br>証跡/LTC-037_5_run1_現金不足_lines.txt<br>証跡/LTC-037_6_判定.txt<br>証跡/E2E_統合/report.json |  | 原因: テストデータ(TD-005 現金不足)の誤り(テストウェア)。主の期待値「投資 > 0円の行で現金 ≧ 0円」は552行すべてで成り立った。Fail は入力の確かめ「55〜58歳・62〜63歳・67歳以降に現金が前の行より減った行がある」で、この入力は最初の月から毎月補填して現金が 0 のままになるので、現金が減る行が出ない。テスト実装に報告 |
| LTC-038 | E2E自動テスト | Fail | 証跡/LTC-038_1_end.png<br>証跡/LTC-038_2_end_dump.xml<br>証跡/LTC-038_3_run1_1回目_dump_first.xml<br>証跡/LTC-038_4_run1_1回目_dump_last.xml<br>証跡/LTC-038_5_run1_1回目_lines.txt<br>証跡/LTC-038_6_run2_D_100000_dump_first.xml<br>証跡/LTC-038_7_run2_D_100000_dump_last.xml<br>証跡/LTC-038_8_run2_D_100000_lines.txt<br>証跡/LTC-038_9_run3_D_dump_first.xml<br>証跡/LTC-038_10_run3_D_dump_last.xml<br>証跡/LTC-038_11_run3_D_lines.txt<br>証跡/LTC-038_12_run4_floor_D_2__dump_first.xml<br>証跡/LTC-038_13_run4_floor_D_2__dump_last.xml<br>証跡/LTC-038_14_run4_floor_D_2__lines.txt<br>証跡/LTC-038_15_判定.txt<br>証跡/E2E_統合/report.json | BUG-001、BUG-002 | 原因: テスト対象の不具合。3つの実行とも、不足した月に補填額の20%だけ余分に減る(BUG-001)。D と floor(D÷2) では投資がマイナスになる(BUG-002) | (総資産 − 前の行の総資産) − (収入 − 生活費)\ | < 4円(総資産 300000→77500、収入 0、生活費 200000) / [D] 不足した月の \ | (総資産 |
| LTC-039 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  |  |
| LTC-040 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  |  |
| LTC-041 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  |  |
| LTC-042 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  | 1回目(証跡/E2E)はエミュレータの不調(Pixel Launcher の ANR とシステムの Watchdog、アプリの ANR)でスクリプトが途中で止まったので、エミュレータを再起動して流し直した結果(証跡/E2E_再実行)。証跡は 証跡/E2E_再実行/evidence/LTC-042/ |
| LTC-043 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  | 1回目(証跡/E2E)はエミュレータの不調(Pixel Launcher の ANR とシステムの Watchdog、アプリの ANR)でスクリプトが途中で止まったので、エミュレータを再起動して流し直した結果(証跡/E2E_再実行)。証跡は 証跡/E2E_再実行/evidence/LTC-043/ |
| LTC-044 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  | 1回目(証跡/E2E)はエミュレータの不調(Pixel Launcher の ANR とシステムの Watchdog、アプリの ANR)でスクリプトが途中で止まったので、エミュレータを再起動して流し直した結果(証跡/E2E_再実行)。証跡は 証跡/E2E_再実行/evidence/LTC-044/ |
| LTC-045 | E2E自動テスト | Fail | 証跡/LTC-045_1_after_delete.xml<br>証跡/LTC-045_2_before_delete.xml<br>証跡/LTC-045_3_end.png<br>証跡/LTC-045_4_end_dump.xml<br>証跡/LTC-045_5_判定.txt<br>証跡/E2E_統合/report.json | BUG-003 | 原因: テスト対象の不具合。1行目の削除を押すと最後の行が消えた(画面 (35,…)、(40,…)) |
| LTC-046 | E2E自動テスト | Fail | 証跡/LTC-046_1_after_delete.xml<br>証跡/LTC-046_2_before_delete.xml<br>証跡/LTC-046_3_end.png<br>証跡/LTC-046_4_end_dump.xml<br>証跡/LTC-046_5_判定.txt<br>証跡/E2E_統合/report.json | BUG-003 | 原因: テスト対象の不具合。2行目の削除を押すと最後の行が消えた |
| LTC-047 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  |  |
| LTC-048 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  |  |
| LTC-049 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  | 1回目(証跡/E2E)はエミュレータの不調(Pixel Launcher の ANR とシステムの Watchdog、アプリの ANR)でスクリプトが途中で止まったので、エミュレータを再起動して流し直した結果(証跡/E2E_再実行)。証跡は 証跡/E2E_再実行/evidence/LTC-049/ |
| LTC-050 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  | 1回目(証跡/E2E)と2回目(証跡/E2E_再実行)はエミュレータの不調(アプリの ANR など)でスクリプトが途中で止まったので、3回目(証跡/E2E_再実行2)の結果。証跡は 証跡/E2E_再実行2/evidence/LTC-050/ |
| LTC-051 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  | 1回目(証跡/E2E)はエミュレータの不調(Pixel Launcher の ANR とシステムの Watchdog、アプリの ANR)でスクリプトが途中で止まったので、エミュレータを再起動して流し直した結果(証跡/E2E_再実行)。証跡は 証跡/E2E_再実行/evidence/LTC-051/ |
| LTC-052 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  | 1回目(証跡/E2E)はエミュレータの不調(Pixel Launcher の ANR とシステムの Watchdog、アプリの ANR)でスクリプトが途中で止まったので、エミュレータを再起動して流し直した結果(証跡/E2E_再実行)。証跡は 証跡/E2E_再実行/evidence/LTC-052/ |
| LTC-053 | E2E自動テスト | Fail | 証跡/LTC-053_1_end.png<br>証跡/LTC-053_2_end_dump.xml<br>証跡/LTC-053_3_run1_1件_dump_first.xml<br>証跡/LTC-053_4_run1_1件_dump_last.xml<br>証跡/LTC-053_5_run1_1件_lines.txt<br>証跡/LTC-053_6_判定.txt<br>証跡/E2E_統合/report.json | BUG-004 | 1回目(証跡/E2E)はエミュレータの不調(Pixel Launcher の ANR とシステムの Watchdog、アプリの ANR)でスクリプトが途中で止まったので、エミュレータを再起動して流し直した結果(証跡/E2E_再実行)。原因: テスト対象の不具合。`[年収: ¥5,000,000]` が240回(変わったあとの毎月)出る。期待値の読み方は Q-021 の回答で変わりうる |
| LTC-054 | E2E自動テスト | Fail | 証跡/LTC-054_1_end.png<br>証跡/LTC-054_2_end_dump.xml<br>証跡/LTC-054_3_run1_2件_dump_first.xml<br>証跡/LTC-054_4_run1_2件_dump_last.xml<br>証跡/LTC-054_5_run1_2件_lines.txt<br>証跡/LTC-054_6_判定.txt<br>証跡/E2E_統合/report.json | BUG-004 | 1回目(証跡/E2E)はエミュレータの不調(Pixel Launcher の ANR とシステムの Watchdog、アプリの ANR)でスクリプトが途中で止まったので、エミュレータを再起動して流し直した結果(証跡/E2E_再実行)。原因: テスト対象の不具合(BUG-004 と同じ)。240回出る |
| LTC-055 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  | 1回目(証跡/E2E)はエミュレータの不調(Pixel Launcher の ANR とシステムの Watchdog、アプリの ANR)でスクリプトが途中で止まったので、エミュレータを再起動して流し直した結果(証跡/E2E_再実行)。証跡は 証跡/E2E_再実行/evidence/LTC-055/ |
| LTC-056 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  | 1回目(証跡/E2E)はエミュレータの不調(Pixel Launcher の ANR とシステムの Watchdog、アプリの ANR)でスクリプトが途中で止まったので、エミュレータを再起動して流し直した結果(証跡/E2E_再実行)。証跡は 証跡/E2E_再実行/evidence/LTC-056/ |
| LTC-057 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  | 1回目(証跡/E2E)はエミュレータの不調(Pixel Launcher の ANR とシステムの Watchdog、アプリの ANR)でスクリプトが途中で止まったので、エミュレータを再起動して流し直した結果(証跡/E2E_再実行)。証跡は 証跡/E2E_再実行/evidence/LTC-057/ |
| LTC-058 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  | 1回目(証跡/E2E)はエミュレータの不調(Pixel Launcher の ANR とシステムの Watchdog、アプリの ANR)でスクリプトが途中で止まったので、エミュレータを再起動して流し直した結果(証跡/E2E_再実行)。証跡は 証跡/E2E_再実行/evidence/LTC-058/ |
| LTC-059 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  | 1回目(証跡/E2E)はエミュレータの不調(Pixel Launcher の ANR とシステムの Watchdog、アプリの ANR)でスクリプトが途中で止まったので、エミュレータを再起動して流し直した結果(証跡/E2E_再実行)。証跡は 証跡/E2E_再実行/evidence/LTC-059/ |
| LTC-060 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  | 1回目(証跡/E2E)はエミュレータの不調(Pixel Launcher の ANR とシステムの Watchdog、アプリの ANR)でスクリプトが途中で止まったので、エミュレータを再起動して流し直した結果(証跡/E2E_再実行)。証跡は 証跡/E2E_再実行/evidence/LTC-060/ |
| LTC-061 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  | 1回目(証跡/E2E)はエミュレータの不調(Pixel Launcher の ANR とシステムの Watchdog、アプリの ANR)でスクリプトが途中で止まったので、エミュレータを再起動して流し直した結果(証跡/E2E_再実行)。証跡は 証跡/E2E_再実行/evidence/LTC-061/ |
| LTC-062 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  | 1回目(証跡/E2E)はエミュレータの不調(Pixel Launcher の ANR とシステムの Watchdog、アプリの ANR)でスクリプトが途中で止まったので、エミュレータを再起動して流し直した結果(証跡/E2E_再実行)。証跡は 証跡/E2E_再実行/evidence/LTC-062/ |
| LTC-063 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  | 1回目(証跡/E2E)と2回目(証跡/E2E_再実行)はエミュレータの不調(アプリの ANR など)でスクリプトが途中で止まったので、3回目(証跡/E2E_再実行2)の結果。証跡は 証跡/E2E_再実行2/evidence/LTC-063/ |
| LTC-064 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  | 1回目(証跡/E2E)はエミュレータの不調(Pixel Launcher の ANR とシステムの Watchdog、アプリの ANR)でスクリプトが途中で止まったので、エミュレータを再起動して流し直した結果(証跡/E2E_再実行)。証跡は 証跡/E2E_再実行/evidence/LTC-064/ |
| LTC-065 | E2E自動テスト | Fail | 証跡/LTC-065_1_end.png<br>証跡/LTC-065_2_end_dump.xml<br>証跡/LTC-065_3_判定.txt<br>証跡/E2E_統合/report.json |  | 原因: スクリプトの誤り(推測)。スクリプトが途中で止まった(横向きで「開始」を押したあと、結果の行が画面に出るのを待って30秒で止まった)。3回流して3回とも同じ所で止まり(E2E、E2E_再実行、E2E_再実行2)、ANR は出ていない。読み取り用の表示の横向き(6000x1080)では「開始」の下に結果の行が出ても画面の外になり、スクロールしないと outputLine が見えないためと考える。テスト対象の不具合かは判断できない(手動の LTC-075 では横向きで開始して結果が出た)。Pass にしていない。E2E自動テストスクリプト作成に報告 |
| LTC-069 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  | 1回目(証跡/E2E)はエミュレータの不調(Pixel Launcher の ANR とシステムの Watchdog、アプリの ANR)でスクリプトが途中で止まったので、エミュレータを再起動して流し直した結果(証跡/E2E_再実行)。証跡は 証跡/E2E_再実行/evidence/LTC-069/ |
| LTC-070 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  | 1回目(証跡/E2E)はエミュレータの不調(Pixel Launcher の ANR とシステムの Watchdog、アプリの ANR)でスクリプトが途中で止まったので、エミュレータを再起動して流し直した結果(証跡/E2E_再実行)。証跡は 証跡/E2E_再実行/evidence/LTC-070/ |
| LTC-071 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  | 1回目(証跡/E2E)はエミュレータの不調(Pixel Launcher の ANR とシステムの Watchdog、アプリの ANR)でスクリプトが途中で止まったので、エミュレータを再起動して流し直した結果(証跡/E2E_再実行)。証跡は 証跡/E2E_再実行/evidence/LTC-071/ |
| LTC-076 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  |  |
| LTC-077 | E2E自動テスト | Pass | 証跡/E2E_統合/report.json |  |  |
| LTC-078 | E2E自動テスト | Fail | 証跡/LTC-078_1_end.png<br>証跡/LTC-078_2_end_dump.xml<br>証跡/LTC-078_3_run1_給与変更1件_dump_first.xml<br>証跡/LTC-078_4_run1_給与変更1件_dump_last.xml<br>証跡/LTC-078_5_run1_給与変更1件_lines.txt<br>証跡/LTC-078_6_run2_給与変更なし_dump_first.xml<br>証跡/LTC-078_7_run2_給与変更なし_dump_last.xml<br>証跡/LTC-078_8_run2_給与変更なし_lines.txt<br>証跡/LTC-078_9_判定.txt<br>証跡/LTC-078_10_削除して開始し直した_dump_first.xml<br>証跡/LTC-078_11_削除して開始し直した_dump_last.xml<br>証跡/LTC-078_12_削除して開始し直した_lines.txt<br>証跡/E2E_統合/report.json | BUG-004 | 1回目(証跡/E2E)と2回目(証跡/E2E_再実行)はエミュレータの不調(アプリの ANR など)でスクリプトが途中で止まったので、3回目(証跡/E2E_再実行2)の結果。原因: テスト対象の不具合(BUG-004)。1回目の結果に `[年収: ¥5,000,000]` が240回出る。ほかの確認(給与変更の効く月、削除して開始し直した結果が給与変更なしと同じ)は成り立った |
| LTC-079 | E2E自動テスト | Fail | 証跡/LTC-079_1_end.png<br>証跡/LTC-079_2_end_dump.xml<br>証跡/LTC-079_3_run1_2件_dump_first.xml<br>証跡/LTC-079_4_run1_2件_dump_last.xml<br>証跡/LTC-079_5_run1_2件_lines.txt<br>証跡/LTC-079_6_判定.txt<br>証跡/E2E_統合/report.json | BUG-004 | 1回目(証跡/E2E)はエミュレータの不調(Pixel Launcher の ANR とシステムの Watchdog、アプリの ANR)でスクリプトが途中で止まったので、エミュレータを再起動して流し直した結果(証跡/E2E_再実行)。原因: テスト対象の不具合(BUG-004)。`[年収: ¥N]` が240回出る |
