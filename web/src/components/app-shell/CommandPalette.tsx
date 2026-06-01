import { SearchOutlined } from "@ant-design/icons";
import { AutoComplete, Modal } from "antd";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useDynamicMenu } from "@/hooks/useDynamicMenu";
import { useStaffSession } from "@/hooks/useStaffSession";

import { NAV_GROUPS, type NavItem } from "./nav-config";
import { PATH_TO_PERM } from "./perm-map";

function canAccess(
  item: NavItem,
  role: string | null,
  matrix: ReturnType<typeof useDynamicMenu>["matrix"],
): boolean {
  const permKey = PATH_TO_PERM[item.to];
  if (matrix && permKey && role) return matrix.matrix[role]?.[permKey] === true;
  return !item.roles || (role != null && item.roles.includes(role));
}

type Option = { value: string; label: React.ReactNode; to: string; search: string };

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const nav = useNavigate();
  const { role } = useStaffSession();
  const { matrix } = useDynamicMenu();

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  // 拍平 NAV_GROUPS 为 AutoComplete options，按分组分类（用 antd 的 OptGroup 形式）
  const options = useMemo(() => {
    return NAV_GROUPS.map((group) => {
      const visible = group.items.filter((i) => canAccess(i, role, matrix));
      if (visible.length === 0) return null;
      return {
        label: <span className="text-xs text-gray-500">{group.label}</span>,
        options: visible.map<Option>((i) => ({
          value: `${group.label} · ${i.label}`,
          label: (
            <span className="flex items-center gap-2">
              <i.icon size={14} aria-hidden />
              {i.label}
            </span>
          ),
          to: i.to,
          search: `${group.label} ${i.label} ${i.to}`,
        })),
      };
    }).filter(Boolean) as { label: React.ReactNode; options: Option[] }[];
  }, [role, matrix]);

  // antd AutoComplete 在使用嵌套 OptGroup 时，option 类型是 group | leaf 的 union；
  // 用 unknown + 字段探测做类型 guard，避免 as never 的硬转换。
  function filter(input: string, option?: unknown): boolean {
    const leaf = option as { search?: string } | undefined;
    if (!leaf?.search) return false;
    return leaf.search.toLowerCase().includes(input.toLowerCase());
  }

  return (
    <Modal
      open={open}
      onCancel={() => setOpen(false)}
      footer={null}
      closable={false}
      width={520}
      styles={{ body: { padding: 16 } }}
      destroyOnClose
    >
      <AutoComplete
        autoFocus
        size="large"
        style={{ width: "100%" }}
        options={options}
        placeholder="搜索菜单…"
        prefix={<SearchOutlined />}
        filterOption={filter as never}
        onSelect={(_value, option) => {
          // option 来自 OptGroup 的叶子节点，结构上是 Option（含 to）
          const to = (option as unknown as Option).to;
          setOpen(false);
          nav(to);
        }}
      />
    </Modal>
  );
}
