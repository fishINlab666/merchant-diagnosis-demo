# 商户经营全景与预算诊断 Demo

基于 React、TypeScript 和 Vite 的纯静态演示站点，所有演示数据均为合成样本。

## 在线演示与自动部署

- 正式站点：https://fishinlab666.github.io/merchant-diagnosis-demo/
- 推送到 `main` 后，`Deploy main to GitHub Pages` 工作流会自动构建并发布。
- 同一仓库内的 Pull Request 会由 `Deploy PR previews` 工作流发布到 `pr-preview/pr-<编号>/`，PR 关闭后自动移除预览。
- Pages 发布源为 `gh-pages` 分支根目录；主站发布会保留 PR 预览目录。

## 本地开发

```bash
npm ci
npm run dev
```

## 验证

```bash
npm run lint
npm run test:unit
npm run build
npm run test:e2e
```

---

This template provides a minimal setup to get React working in Vite with HMR and some Oxlint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the Oxlint configuration

If you are developing a production application, we recommend enabling type-aware lint rules by installing `oxlint-tsgolint` and editing `.oxlintrc.json`:

```json
{
  "$schema": "./node_modules/oxlint/configuration_schema.json",
  "plugins": ["react", "typescript", "oxc"],
  "options": {
    "typeAware": true
  },
  "rules": {
    "react/rules-of-hooks": "error",
    "react/only-export-components": ["warn", { "allowConstantExport": true }]
  }
}
```

See the [Oxlint rules documentation](https://oxc.rs/docs/guide/usage/linter/rules) for the full list of rules and categories.
