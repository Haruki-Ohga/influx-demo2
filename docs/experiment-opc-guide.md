# OPC 実験ログの取り込みガイド

`data/experiment_opc_log/` ディレクトリにはサンプルの OPC 実験ログが CSV 形式で格納されています。このガイドでは、同梱の `python/write_experiment_opc_csv.py` スクリプトを使ってデータを InfluxDB にロードし、Grafana で可視化するまでの流れをまとめます。

## 前提条件

- Docker Compose でこのリポジトリの InfluxDB / Grafana を起動済みであること
- Python 3.9 以上 (標準の `zoneinfo` モジュールを使用)
- `requirements.txt` に基づき依存パッケージをインストール済み

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

環境変数で接続情報を上書きする場合は `INFLUX_URL`、`INFLUX_TOKEN`、`INFLUX_ORG`、`INFLUX_BUCKET` などを設定してください。

## データの投入

スクリプトは指定ディレクトリ（デフォルトは `data/experiment_opc_log`）内のすべての CSV を走査し、measurement 単位で InfluxDB に投入します。最低限必要なコマンドは次のとおりです。

```bash
python python/write_experiment_opc_csv.py \
  --bucket demo-bucket \
  --org demo-org \
  --measurement experiment_opc
```

主なオプション:

| オプション | 既定値 | 説明 |
|------------|--------|------|
| `--csv-dir` | `data/experiment_opc_log` | 読み込む CSV のディレクトリ |
| `--timestamp-format` | `%Y-%m-%d %H:%M:%S` | CSV の `timestamp` 列の書式 |
| `--timezone` | `UTC` | ナイーブなタイムスタンプに適用するタイムゾーン。`NAIVE` を指定すると変換しません |
| `--batch-size` | `500` | 一度に書き込むポイント数 |

引数は同名の環境変数 (`INFLUX_MEASUREMENT`、`OPC_CSV_DIR` など) で上書きすることもできます。スクリプトは既存データのフィールド型を自動的に検出し、フォーマットに合わない値をスキップした件数を標準出力に表示します。

投入が完了すると、処理したファイル数や書き込んだポイント数が表示されます。異常終了した場合は CSV の `timestamp` 列のフォーマットや空欄を確認してください。

## Grafana で確認する

1. ブラウザで `http://localhost:3000` にアクセスし、Grafana にログインします。
2. 左メニューから **Explore** もしくは **Dashboards → New → Visualization** を選択します。
3. データソースに `InfluxDB` を選び、次の Flux クエリを実行します。

   ```flux
   from(bucket: "demo-bucket")
     |> range(start: -24h)
     |> filter(fn: (r) => r._measurement == "experiment_opc")
   ```

4. `_field` やタグ (`source_file` など) で絞り込み、グラフや統計テーブルを作成します。

ダッシュボードとして保存・再利用したい場合は、既存の JSON を複製し `grafana/provisioning/dashboards/` に追加してください。詳しくは `docs/adding-new-data.md` を参照してください。

## トラブルシューティング

- **CSV が見つからない**: `--csv-dir` のパスが正しいか確認してください。空ディレクトリの場合はエラーになります。
- **タイムゾーンを変換したくない**: `--timezone NAIVE` を指定すると、CSV のタイムスタンプをそのまま利用します。
- **値が取り込まれない**: 空文字や型変換に失敗した値はスキップされます。実行結果に出力される `Skipped non-numeric values` のメッセージで確認できます。

これで OPC 実験ログの取り込みと可視化が完了します。別のデータ種別を追加したい場合は `docs/adding-new-data.md` も役立ちます。
