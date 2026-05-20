#!/usr/bin/env bash
# 校验 commit message 符合 Conventional Commits 格式
set -e

msg_file="$1"
[[ -z "$msg_file" ]] && { echo "usage: $0 <msg-file>"; exit 1; }

# 跳过 merge / revert / fixup 自动消息
first_line=$(head -n1 "$msg_file")
case "$first_line" in
    "Merge "*|"Revert "*|"fixup!"*|"squash!"*) exit 0 ;;
esac

pattern='^(feat|fix|refactor|test|docs|chore|perf|build|ci|style)(\([a-z0-9-]+\))?: .{1,72}$'
if [[ ! "$first_line" =~ $pattern ]]; then
    cat >&2 <<EOF
ERROR: commit message 不符合 Conventional Commits 格式

格式：  <type>(<scope>): <subject>
types:  feat | fix | refactor | test | docs | chore | perf | build | ci | style
scopes: mvp-1 | mvp-2 | mvp-3 | spec | plan | docs | engine | web | staff | db | prompt
长度:   subject ≤ 72 字符

示例:   feat(mvp-1): 添加 search_code 工具（Sourcegraph GraphQL）
       fix(engine): tool_router 漏注入 conversation_id
       docs(spec): §13.10 加 tawk.to 并存期

你的:   $first_line
EOF
    exit 1
fi
