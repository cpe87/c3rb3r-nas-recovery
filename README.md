# NAS Recovery Public — experimental prototype

作者 / Author: **cpe87**

本项目的开发者署名不替代上游项目的版权与许可声明。
Author attribution does not replace upstream copyright and license notices.

## 中文

这是独立公用试用原型，未在多种 NAS 上实测，不是已验证的通用恢复产品。程序默认样本模式，每次最多处理 10 个文件。正式批量使用前请核验样本与输出盘。

### 开发语言和环境

- Python 3.11+，Tkinter/Tcl-Tk 桌面界面，首要运行平台为 Windows 10/11。
- Paramiko 用于 SSH/SFTP，Pillow 用于图片完整解码；安装版内置 FFmpeg 用于视频完整解码，源码版也可自行指定。
- NAS 需要 Python 3、sudo、Btrfs 查询工具和 SSH。NAS 端仅依赖 Python 标准库及附带模块。

### 安装和使用

Windows 实验安装版 0.1.3：运行 `NAS-Recovery-Public-0.1.3-windows-x64-setup.exe`，安装后从开始菜单打开。已内置 Python 和从官方源码编译的 FFmpeg 校验版，视频校验路径自动填入。支持 Windows 10/11 x64；安装不连接 NAS。以下是源码版的安装方式。

1. 需要带 Tcl/Tk 的 Python 3.11 或更新版本。安装脚本会自动查找 Python Launcher、PATH、常见安装目录和已有 Codex 运行环境，不要求必须有 `py` 命令。未找到时会提示安装 Python。
2. 运行 `setup.cmd` 安装独立虚拟环境，再运行 `start.cmd`。
3. 填写自己的 NAS 地址、SSH 端口、用户名、密码，首次连接向 NAS 管理员核对 SSH 指纹。
4. 读取目录，双击进入子目录，多选添加；也可逐行填写以 `/volume数字` 开头的路径。
5. 选择图片、视频、其他类型，选择独立硬盘上的输出根目录；视频需指定 FFmpeg。
6. 保持样本模式运行，检查得到的文件、时长、日志，再决定是否取消样本限制。

SSH 密码暂存在运行内存，用于 sudo，不写入配置。第一次使用的主机指纹只在本次运行中固定，重启后需重新核对。SFTP 只把本次脚本、任务配置放入 NAS `/dev/shm`，任务结束后内存盘任务文件暂时保留。不需要安装 NAS 套件。

### 支持范围与限制

- 结构符合当前解析器的 `.L0CK3D` 文件，支持解析 0x24/0x25/0x26 参数。后缀和结构匹配不能独立证明勒索家族。
- 只尝试从当前保留引用重建旧块，必须有完整无歧义映射、旧块 CRC32C 和可比较的明文锚点。全量加密通常需要其他历史线索，本原型不做旧树根全盘搜索。
- 严格限制 Btrfs 单底层设备、DATA single、4 KiB 扇区和 CRC32C。不支持多设备 Btrfs、压缩或 inline extent 等情况。
- 上限为每文件 4 GiB，输出盘始终预留 20 GiB。输出设备是否独立，需要用户依据物理连接确认，程序不能证明外接盘与 NAS 存储池的物理关系。
- 不读取隐藏系统目录或勒索说明。无扩展名及未识别类型属于“其他”。其他文件没有通用完整性验证器，以 `__needs_review` 保存。
- HEIC/RAW 等可能缺少解码器，保留待核验候选。LRF 按视频尝试验证。
- 视频成功表示恢复候选按容器时长完整解码；无独立原件证明。输出标有 `__duration_unverified`。
- 进度 100% 表示队列处理结束，失败和待核验不算完整恢复成功。
- 当前没有自动断线续传或任务历史界面。中断后候选与 JSON 记录保留。再次选择目录会重读，已存在内容哈希相同则复用，不同则另名保存。
- 同一程序实例只允许一个任务。不要从多个实例对同一目标并行恢复。

保留 NAS 公网隔离。不得运行文件系统维护、原地解密或在受害存储池写输出。可行时先制作完整数据取证镜像；元数据镜像不能代替完整镜像。

### 结果与隐私

输出按 `volume1/...` 等 NAS 原路径保存。每次任务的清单、映射、校验记录及失败候选位于 `_recovery_records`。记录会包含使用者自己的文件路径，分享报告前自行脱敏。源码目录没有预填任何个人账号、私钥、IP、受害存储池 UUID 或实际案例文件。

### 分发

`engine/btrfs_source.py` 的低层读取代码基于 crt106/c3rb3r-btrfs-recovery，保留其 MIT 许可证于 `THIRD_PARTY_LICENSES/crt106-MIT.txt`。其余原型代码见 LICENSE。安装版捆绑 Python、依赖及 FFmpeg，并附许可证与来源说明，不捆绑凭据或恢复记录。

0.1.3 的 FFmpeg 从官方 n9.0.2 源码编译，不启用外部多媒体库、GPL/nonfree 组件和网络功能，当前构建使用 LGPL-2.1-or-later。完整 FFmpeg 源码、匹配的编译工具链源码、构建脚本、配置和 SHA-256 已放入安装目录 `_internal/source/FFmpeg-9.0.2-corresponding-source.zip`，另提供同名下载包。FFmpeg 可独立替换，没有限制修改、调试或重新构建。关闭独立汇编优化可能降低解码速度。具体来源见 `THIRD_PARTY_LICENSES/FFmpeg-SOURCE.txt`。

发布时保留实验版标识、适用范围、许可证和源码包；不要宣传未经验证的恢复成功率。FFmpeg 分发材料齐备不代表恢复引擎已通过跨型号 NAS 实测。

## English

This is an independent experimental prototype, not a validated general-purpose recovery product. Python 3.11+, Tkinter, Paramiko, Pillow and a user-provided FFmpeg executable are used. Windows 10/11 is the primary platform. NAS prerequisites are SSH, Python 3, sudo and Btrfs query tools.

Run `setup.cmd`, then `start.cmd`. Enter your own connection details, verify the SSH host fingerprint, select directories and media types, and select physically independent output storage. Passwords are held in memory only. Start with pilot mode (at most 10 files). The Chinese/English selector switches the interface; technical diagnostics may remain in their original language.

Supported scope is compatible .L0CK3D layouts on a single-device Btrfs DATA single filesystem with 4 KiB sectors and CRC32C. Retained uncompressed extents require complete unambiguous mapping, checksums and plaintext anchors. File size is limited to 4 GiB. No old-root scanning, whole-disk imaging, in-place repair, or automatic reconnect/resume is provided. Hidden system directories and ransom notes are excluded. Full encryption may require historical evidence this prototype cannot obtain.

Full video decode does not establish identity with an independent original. Unsupported formats remain review candidates. 100% means all queued files were attempted. Keep the NAS isolated from the Internet and acquire a complete forensic image when feasible. Output storage independence must be confirmed by the user.

Outputs retain NAS directory structure. `_recovery_records` stores inventory, mapping evidence, hashes and partial candidates. These user-created reports contain personal filenames and should be redacted before sharing. The distributed source contains no case credentials or private data. See LICENSE and THIRD_PARTY_LICENSES. Broader release requires multi-environment testing and a security/license review.
