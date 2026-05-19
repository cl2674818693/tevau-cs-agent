# Task 17: docker-compose 升级 + 部署文档

> MVP-2 plan 拆分文件 — 总览见 [README.md](./README.md)。

**Files:**
- Modify: `docker-compose.yml`（加 MySQL 用于本地开发；生产连阿里云 RDS）
- Modify: `README.md`

- [ ] **Step 1: docker-compose 加 MySQL 本地服务**（仅 dev，生产用阿里云 RDS）

```yaml
services:
  # ... api / web / sourcegraph 同 MVP-1 ...
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: rootpass
      MYSQL_DATABASE: unlimitpay_test
      MYSQL_USER: tevau_test_read
      MYSQL_PASSWORD: ${MYSQL_PASSWORD}
    ports: ["3306:3306"]
    volumes:
      - mysql-data:/var/lib/mysql
      - ./tests/fixtures/unlimitpay_seed.sql:/docker-entrypoint-initdb.d/01-seed.sql:ro
volumes:
  mysql-data:
```

- [ ] **Step 2: README 加 MVP-2 启动说明**（C 端 JWT 公钥配置 / 客服账号初始化 / staff_jwt_secret 生成）

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml README.md
git commit -m "chore(mvp-2): docker-compose 加 mysql 本地服务 + 部署文档更新"
```

---
