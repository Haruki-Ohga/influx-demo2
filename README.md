# InfluxDB + Grafana 最小構成

Docker Compose を用いて InfluxDB 2.x と Grafana を起動し、時系列データの可視化をすぐに始められる最小構成を用意しました。

## 構成

- `docker-compose.yml`  
  InfluxDB と Grafana を起動します。初期ユーザー／バケットが自動作成されます。
- `grafana/provisioning/datasources/datasource.yml`  
  Grafana 起動時に InfluxDB データソースを自動登録します。
- `grafana/provisioning/dashboards/sample-dashboard.json`  
  例として CPU 使用率を想定したタイムシリーズダッシュボードを自動登録します。

### デフォルトの資格情報

| サービス | ユーザー | パスワード | 備考 |
|----------|----------|------------|------|
| InfluxDB | `admin`  | `admin1234` | `demo-token` (管理用トークン) |
| Grafana  | `admin`  | `grafana1234` | 初回ログイン後に変更推奨 |

> **注意:** 実運用では必ずトークン・パスワードを変更し、`.env` などで管理してください。

## 前提条件

- Docker (24 以降推奨)
- Docker Compose v2 (`docker compose` コマンドが利用できること)

## 起動手順

```bash
# コンテナ起動
docker compose up -d

# 初回はイメージのダウンロードに時間がかかる場合があります
```

起動後の確認:

```bash
# InfluxDB が Listen しているか確認
curl -s http://localhost:8086/health | jq

# Grafana のログを確認（任意）
docker compose logs -f grafana
```

## データの投入例

初期化済みの組織・バケット:

- 組織: `demo-org`
- バケット: `demo-bucket`
- トークン: `demo-token`

Flux Line Protocol を使い、CPU 使用率のサンプルメトリクスを投入します。

```bash
curl -X POST "http://localhost:8086/api/v2/write?org=demo-org&bucket=demo-bucket&precision=ns" \
  -H "Authorization: Token demo-token" \
  -H "Content-Type: text/plain; charset=utf-8" \
  --data-raw "cpu,host=server01 usage_user=42.5 $(date +%s%N)"
```

## Grafana での可視化

1. ブラウザで `http://localhost:3000` にアクセス
2. ログイン: `admin` / `grafana1234`
3. 左メニューの **Dashboards → Browse** から `InfluxDB Sample Dashboard` を開く

ダッシュボードは `demo-bucket` に保存された `_measurement = cpu` / `_field = usage_user` のデータを 1 分平均で表示します。必要に応じて Flux クエリを編集してください。

## Python サンプルプログラム

`python/write_sample.py` は Python から InfluxDB にデータを書き込む最小例です。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 環境変数で接続情報を上書き可能
export INFLUX_URL=http://localhost:8086
export INFLUX_TOKEN=demo-token
export INFLUX_ORG=demo-org
export INFLUX_BUCKET=demo-bucket

python python/write_sample.py
```

環境変数を設定しない場合は `docker-compose.yml` のデフォルト値が使われます。書き込まれるポイントは `cpu` 計測 (usage_user) のランダム値です。

### Python で値を読む

`python/read_sample.py` は直近のデータポイントを Flux クエリで取得し、標準出力に表示します。

```bash
source .venv/bin/activate  # まだの場合は上記手順で作成

export INFLUX_LIMIT=5          # 取得件数（任意）
export INFLUX_RANGE=-6h        # 観測期間（Flux range 形式）
export INFLUX_MEASUREMENT=cpu  # 取得したい測定
export INFLUX_FIELD=usage_user # 取得したいフィールド

python python/read_sample.py
```

環境変数を省略した場合はデフォルト値 (`cpu` / `usage_user` / `-1h` / 10件) が使われます。

## よく使うコマンド

```bash
# コンテナ停止
docker compose down

# ボリュームも含めて削除（初期化したい場合）
docker compose down -v

# Influx CLI を使って REPL に入る（必要に応じてコンテナ内に入る）
docker compose exec influxdb influx
```

## カスタマイズのヒント

- 認証情報を `.env` に分離し、`docker-compose.yml` 内で参照 (`${VAR_NAME}`) すると安全です。
- 追加のダッシュボードは `grafana/provisioning/dashboards/` 以下に JSON を置くことで自動登録できます。
- InfluxDB のリテンションポリシーを変更したい場合は `DOCKER_INFLUXDB_INIT_RETENTION` を編集してください (`0` は無制限)。
- 別種のメトリクスを追加する際の具体的な手順は `docs/adding-new-data.md` を参照してください。

---

何か問題があれば `docker compose logs <service>` で各サービスのログを確認してください。
