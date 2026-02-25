# EasiCoin 永续合约交易终端

这是一个基于 Python 3.11+ 的异步量化交易终端示例，包含 REST/WS 客户端、服务层、Pydantic 模型以及 Textual 控制台 TUI。

## 功能特性

- 异步 REST/WS 客户端（aiohttp）
- 签名认证（HMAC-SHA256）
- Pydantic v2 模型与数据校验
- Rich + Textual 控制台终端界面
- 基础风险控制与网格示例
- 日志与交易记录落盘
- 优雅退出与持仓快照保存

## 目录结构

```
config/
core/
models/
services/
ui/
utils/
main.py
requirements.txt
.env.example
```

## 环境要求

- Python 3.11+

## 安装依赖

```bash
pip install -r requirements.txt
```

## 配置说明

复制并编辑环境变量：

```bash
cp .env.example .env
```

在 .env 中填写：

- EASICOIN_API_KEY
- EASICOIN_API_SECRET
- EASICOIN_API_BASE_URL
- EASICOIN_WS_BASE_URL

如未填写 Key/Secret，运行时会提示安全输入（建议使用系统密钥库加密保存）。

## 运行

```bash
python main.py
```

## 常用命令

在底部命令输入栏中可尝试：

- buy 0.01 BTCUSDT @ market
- sell 0.02 BTCUSDT @ market
- leverage 20
- close all

## 日志与数据

- 日志文件：`logs/app.log`
- 交易记录：`data/trades.csv`
- 持仓快照：`data/positions_<timestamp>.json`

## 注意事项

- 当前 UI 使用模拟数据进行刷新展示，可逐步替换为真实行情/账户推送。
- 私有接口请确保 API 权限正确。

## 许可

仅用于学习和研究用途。
