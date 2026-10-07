# ScrollFlow

一个本地运行的“网页 → 自动滚动 GIF”小工具。

## 为什么不是纯 HTML？

浏览器安全策略会阻止普通网页直接读取/截图任意第三方网页（CORS、Same-Origin Policy、`X-Frame-Options`、CSP）。ScrollFlow 因此采用：

- 前端：本地网页界面
- 后端：Python + Flask
- 浏览器：Playwright Chromium
- GIF：Pillow

这样可以真正打开目标网页并逐帧截图，而不是依赖 iframe。

## macOS / Linux

首次使用：

```bash
cd scrollflow_gif_tool
chmod +x install_and_run.command
./install_and_run.command
```

之后直接：

```bash
./run.command
```

macOS 也可以在 Finder 里双击 `install_and_run.command`；之后双击 `run.command` 即可。

## Windows

首次双击：

```text
install_and_run.bat
```

之后双击：

```text
run.bat
```

浏览器会自动打开：

```text
http://127.0.0.1:5178
```

## 推荐参数

- 浏览器：1440 × 900
- GIF 输出宽度：960
- FPS：5
- 滚动速度：760 px/s
- 顶部停留：1.2 s
- 底部停留：1.0 s
- 最长滚动：24 s

网页越长、FPS 越高、输出越宽，GIF 文件会越大。

## 限制

- 登录后才能看的网页，需要额外实现登录态复用。
- Cloudflare / 验证码 / 强反爬站点可能阻止自动浏览器。
- 无限滚动网页默认只按当前已加载页面高度处理；滚动过程中触发的懒加载内容一般会自然出现。
- 视频、WebGL 或某些浏览器硬件加速动画在 headless 模式下可能和肉眼看到的略有不同。

生成的 GIF 会保存在 `outputs/`。

## 录制前完整预加载

ScrollFlow 会在正式录制前先完成一轮页面准备：等待 `load` 与网络基本空闲、等待 Web Font、快速预滚动整页以触发 lazy-load 图片/区块、等待图片解码与页面高度稳定，然后回到页面顶部。**GIF 的第一帧只会在这些步骤结束后才开始截取**，因此正常网页的加载过程不会被录进 GIF。

> 对无限滚动、持续实时更新或永不停止网络连接的网页，工具会使用超时与最大预滚动步数避免永久等待。

## v3 界面更新

- 初始页重做为浅色“产品展览海报”式首屏。
- URL 输入和开始生成保持在首屏主视觉中，参数默认收起。
- 右侧的“网页 → 胶片 → GIF”装置为真实 HTML/CSS，而不是静态概念图。
- 生成流程与预览区初始隐藏，点击开始生成后自动展开。
- 保留 v2 的完整预加载策略：正式录制前等待页面、字体、图片与 lazy-load 内容稳定。
