# LivingTree AI Agent Desktop

基于 Vue 3 + FastAPI + Electron 的桌面AI助手应用。

## 技术栈

- **前端**: Vue 3 + Naive UI + Pinia
- **后端**: FastAPI + Python
- **桌面**: Electron
- **构建**: Vite

## 开发

```bash
# 安装后端依赖
cd server
pip install -r requirements.txt

# 安装前端依赖
cd ../client
npm install

# 启动后端服务（终端1）
cd server
python main.py

# 启动前端开发（终端2）
cd client
npm run dev

# 启动Electron（终端3）
cd electron
npm install
npm start
```

## 构建

```bash
# 构建前端
cd client
npm run build

# 构建桌面应用
cd electron
npm run build:win
```

## 项目结构

```
desktop/
├── client/          # Vue 3前端
│   ├── src/
│   ├── package.json
│   └── vite.config.js
├── server/          # FastAPI后端
│   ├── api/
│   ├── core/
│   ├── main.py
│   └── requirements.txt
└── electron/        # Electron配置
    ├── main.js
    └── package.json
```