# product-detect 任务台账

## 当前阶段：Phase 1 — 环境安装

### 待办

- [ ] **P1** 安装 Miniconda
  ```bash
  curl -O https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-x86_64.sh
  bash Miniconda3-latest-MacOSX-x86_64.sh
  ```

- [ ] **P1** 创建 yolov8 conda 环境
  ```bash
  conda create -n yolov8 python=3.10
  conda activate yolov8
  pip install -r /Users/chat/claude/product-detect/requirements.txt
  ```

- [ ] **P2** 提供 KGOS 单品素材图 → 放入 `assets/kgos/`（文件名=ERP产品名）

- [ ] **P2** 运行预览确认去背景效果
  ```bash
  python scripts/generate.py --brand kgos --preview
  ```

- [ ] **P2** 生成正式训练数据集（1200张）

- [ ] **P3** 训练 KGOS 模型（yolov8n 先跑）

- [ ] **P4** 集成到 product-mapping

## 已完成

- [x] 项目目录结构创建
- [x] generate.py / train.py / infer.py / verify.py 编写完成
