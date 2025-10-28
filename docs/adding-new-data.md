# 新しいデータ種別の追加ガイド

InfluxDB に別種類のメトリクスを保存し、Grafana で可視化するまでの流れをまとめました。ここでいう「データ種別」は _measurement / field / tag_ の組み合わせを指します。

## 1. スキーマを決める

1. **measurement**: データのカテゴリ。例: `temperature`、`response_time`。
2. **tag**: フィルターやグループ化に使いたい属性。例: `location=tokyo`、`service=api`。文字列で、カードが高すぎないものにします。
3. **field**: 実際の値（数値・真偽値・文字列）。例: `value`、`latency_ms`。インデックスは付きません。

ドキュメント化しておくと後から扱いが楽になります。例えば:

| measurement | fields         | tags                  | 備考             |
|-------------|----------------|-----------------------|------------------|
| `temperature` | `value (float)` | `location`, `sensor` | 摂氏温度を想定 |

## 2. InfluxDB に書き込む

### 2-1. 既存の Python スクリプトを使う

`python/write_sample.py` をテンプレートとして複製します:

```bash
cp python/write_sample.py python/write_temperature.py
```

スクリプト内で以下を調整します。

- `measurement` 変数を新しい measurement に変更 (`temperature` など)。
- `field("usage_user", usage)` のフィールド名や値の生成方式を用途に合わせて変更。
- タグが必要なら `point.tag("location", "tokyo")` のように追加。

環境変数で measurement 名を切り替えたい場合は既存の `INFLUX_MEASUREMENT` 変数を利用できます。フィールド名も切り替えるなら、スクリプトに独自の環境変数（例: `INFLUX_FIELD`）を追加してください。

### 2-2. Line Protocol（curl）で書き込む

CLI からシンプルに送る場合は以下のようにします。

```bash
curl -X POST "http://localhost:8086/api/v2/write?org=demo-org&bucket=demo-bucket&precision=ns" \
  -H "Authorization: Token demo-token" \
  -H "Content-Type: text/plain; charset=utf-8" \
  --data-raw "temperature,location=tokyo,sensor=sensor01 value=23.4 $(date +%s%N)"
```

measurement / tags / fields をスペースとカンマで区切る書式（Line Protocol）さえ守れば、どんなデータでも登録できます。

## 3. データを確認する

Python 製の読み取りスクリプト `python/read_sample.py` で値を確認できます。

```bash
export INFLUX_MEASUREMENT=temperature
export INFLUX_FIELD=value
python python/read_sample.py
```

結果が期待どおりであれば次に進みます。

## 4. Grafana に表示する

### 4-1. UI からパネルを作成する

1. ブラウザで Grafana にログイン。
2. 左メニュー `Dashboards` → `New` → `Visualization` を選択。
3. データソースに `InfluxDB` を選ぶ。
4. Flux クエリを編集し、新しい measurement / field を指定:

   ```flux
   from(bucket: "demo-bucket")
     |> range(start: -6h)
     |> filter(fn: (r) => r._measurement == "temperature")
     |> filter(fn: (r) => r._field == "value")
   ```

5. 可視化タイプ・凡例などを調整し、保存。

### 4-2. 自動プロビジョニングに追加する

リポジトリで管理したい場合は JSON ダッシュボードを新規に作成します。

1. Grafana 上でダッシュボードを構成したら、右上メニューから `Dashboard settings` → `JSON model` を開き、JSON をコピー。
2. リポジトリ内に `grafana/provisioning/dashboards/temperature-dashboard.json` のようなファイル名で保存。
3. `grafana/provisioning/dashboards/dashboard.yml` にそのフォルダが指定されているので、追加のファイルも自動で読み込まれます。
4. 変更後は `docker compose restart grafana` で再読み込みしてください。

JSON を手書きする場合は既存の `sample-dashboard.json` を複製し、`targets[0].query` や `title` を新しい用途に合わせて調整するのが堅実です。

## 5. よくあるポイント

- タグは検索キー、フィールドは値と覚えると整理しやすいです。
- 計測値のスケールが異なる場合は Grafana でパネルを分けるか、ユニット（Unit）設定を合わせましょう。
- プロビジョニングを変更した際は Grafana を再起動するか `docker compose restart grafana` を忘れずに。
- 本番環境ではトークンやパスワードを `.env` などで安全に管理してください。

この手順を踏めば、どんな種類のメトリクスでも InfluxDB → Grafana への流れに追加できます。***
