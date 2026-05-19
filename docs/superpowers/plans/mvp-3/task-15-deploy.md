# Task 15: docker-compose 升级 + 阿里云 Prometheus 抓取配置 + 部署文档

> MVP-3 plan 拆分文件 — 总览见 [README.md](./README.md)。

**Files:**
- Modify: `docker-compose.yml`
- Create: `infra/prometheus-scrape-config.example.yaml`
- Modify: `README.md`

- [ ] **Step 1: docker-compose 调整**
  - 删除 mock event center（生产不需要）
  - 加 `prometheus.scrape: true` 注解（如果用 sidecar 抓取）
  - 加 `OBSERVABILITY_ENABLED=true` env

- [ ] **Step 2: 阿里云 Prometheus 抓取配置示例**

```yaml
# 这段配到阿里云 Prometheus 控制台
- job_name: 'tevau-ai-engine'
  static_configs:
    - targets: ['ai-engine.tevau.internal:8000']
  metrics_path: '/metrics'
  scrape_interval: 15s
```

- [ ] **Step 3: README 加 MVP-3 启动 + 上线 checklist**

包括：事项中心连通性验证、HMAC 双 key 初始化、Grafana dashboard 导入、客服账号批量初始化（前 2 名 APP 客服 + 嘉豪 + 另一对接人 + admin）

- [ ] **Step 4: Commit**

```bash
git commit -m "chore(mvp-3): docker-compose + 阿里云 Prometheus 抓取配置 + 上线 checklist"
```

---
