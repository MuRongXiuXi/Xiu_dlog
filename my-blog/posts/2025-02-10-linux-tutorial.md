---
title: Linux 使用教程（入门到日常够用）
date: 2025-02-10
tags: 技术, Linux
summary: 面向 Ubuntu/Debian 的 Linux 入门笔记：登录、文件管理、装软件、看进程、连服务器、写简单脚本。
---

> 适用：Ubuntu / Debian 为主，其他发行版会标注差异。
> 目标：读完能独立登录、管理文件、装软件、看进程、连服务器、写简单脚本。
> 约定：`$` 表示普通用户提示符，`#` 表示 root；`<...>` 是占位符，替换成你的内容。

---

## 1. Linux 是什么

Linux 严格说是**内核**，我们日常说的“Linux 系统”指内核 + GNU 工具 + 桌面/服务组成的**发行版**。常见发行版：

| 发行版 | 包管理 | 适合 |
| --- | --- | --- |
| Ubuntu / Debian | `apt` | 新手、服务器、资料最多 |
| Fedora / RHEL | `dnf` | 企业、较新的软件 |
| Arch Linux | `pacman` | 想折腾、滚动更新 |
| openSUSE | `zypper` | 企业/桌面兼顾 |

在 Windows 上想先体验，最省事的是 **WSL2**：

```powershell
wsl --install -d Ubuntu
```

装完在开始菜单打开 Ubuntu，按提示设置用户名和密码即可。

---

## 2. 登录与用户

- 本机：图形界面登录，或 `Ctrl+Alt+F3` 切到文字终端。
- 远程：`ssh 用户名@服务器IP`，例如 `ssh alice@192.168.1.10`。
- 首次登录云服务器，通常先用 `root`，再创建普通用户：

```bash
adduser alice              # 创建用户并设置密码
usermod -aG sudo alice     # 加入 sudo 组（Debian/Ubuntu）
su - alice                 # 切换用户
```

- `sudo 命令`：以 root 权限执行一条命令。
- `whoami`：当前用户；`id`：当前用户和所属组。

> 习惯：日常用普通用户 + `sudo`，不要长期开 root。

---

## 3. Shell 基础

打开终端后看到类似：

```
alice@host:~$
```

`~` 是家目录（`/home/alice`）。命令的一般结构：

```
命令 [选项] [参数]
ls -l /var/log
```

### 必会的四个键

| 操作 | 作用 |
| --- | --- |
| `Tab` | 补全命令/路径，按两下列出候选 |
| `↑ / ↓` | 翻历史命令 |
| `Ctrl+C` | 中断当前命令 |
| `Ctrl+L` | 清屏（等价 `clear`） |

### 查帮助

```bash
man ls          # 手册，q 退出，/ 搜索
ls --help       # 简短帮助
apropos 关键词   # 搜索相关命令
```

### 命令组合

```bash
cmd1 ; cmd2     # 顺序执行，不管成败
cmd1 && cmd2    # cmd1 成功才执行 cmd2
cmd1 || cmd2    # cmd1 失败才执行 cmd2
cmd &           # 后台运行
```

---

## 4. 文件与目录

### 看

```bash
pwd                 # 当前路径
ls                  # 列目录
ls -alh             # 全部（含隐藏）、详细信息、人类可读大小
tree -L 2           # 树状两层（可能需要 apt install tree）
```

### 走

```bash
cd /etc             # 进入目录
cd ..               # 上一级
cd ~                # 回家目录
cd -                # 回到上一个目录
```

### 增删改

```bash
mkdir -p a/b/c      # 递归建目录
touch note.txt      # 建空文件 / 更新时间戳
cp file.txt /tmp/   # 复制文件
cp -r dir1 dir2     # 递归复制目录
mv old.txt new.txt  # 重命名
mv file.txt /tmp/   # 移动
rm file.txt         # 删除文件
rm -r dir           # 递归删除目录（危险）
rm -rf dir          # 强制递归删除（更危险，确认路径再敲）
ln -s /opt/app/bin/app ~/app   # 软链接
```

> `rm` 没有回收站。重要数据先备份，删前用 `ls` 确认路径。

### 通配符

```bash
ls *.log            # 所有 .log
ls file?.txt        # 单个字符
ls [abc]*           # a/b/c 开头
```

---

## 5. 查看文件内容

```bash
cat file.txt            # 全部输出（小文件）
less file.txt           # 分页查看，q 退出，/ 搜索
head -n 20 file.txt     # 前 20 行
tail -n 20 file.txt     # 后 20 行
tail -f app.log         # 实时跟踪日志，Ctrl+C 退出
wc -l file.txt          # 行数
grep "error" app.log    # 搜关键词
grep -rn "TODO" src/    # 递归搜并显示行号
```

---

## 6. 权限

`ls -l` 的第一列如 `-rw-r--r--`：

```
-  rw-  r--  r--
类型 属主 属组 其他人
```

- `r` 读(4)、`w` 写(2)、`x` 执行(1)。
- 目录的 `x` 表示“能进入”，`w` 表示“能在里面增删文件”。

### 改权限

```bash
chmod 755 script.sh     # rwxr-xr-x
chmod 644 file.txt      # rw-r--r--
chmod +x script.sh      # 加执行权限
chmod -R 750 dir        # 递归
```

### 改属主

```bash
sudo chown alice:alice file.txt
sudo chown -R www-data:www-data /var/www
```

### 默认权限 umask

```bash
umask          # 常见 022 → 新文件 644，新目录 755
umask 027      # 更严格
```

> `Permission denied` 先看 `ls -l` 的属主和权限，再决定 `chmod` 还是 `sudo`。

---

## 7. 查找

```bash
find . -name "*.log"              # 当前目录下按名找
find /var -type f -size +100M     # 大于 100M 的文件
find . -mtime +7 -name "*.tmp"    # 7 天前修改的
find . -name "*.log" -delete      # 找到并删除（先去掉 -delete 预览）
which python3                     # 命令路径
whereis nginx                     # 程序/手册位置
```

---

## 8. 软件包管理

### Debian / Ubuntu（apt）

```bash
sudo apt update                 # 更新软件索引
sudo apt upgrade                # 升级已安装软件
sudo apt install nginx          # 安装
sudo apt remove nginx           # 卸载（保留配置）
sudo apt purge nginx            # 卸载并删配置
apt search 关键词                # 搜索
apt show nginx                  # 包信息
```

### Fedora / RHEL（dnf）

```bash
sudo dnf install nginx
sudo dnf remove nginx
sudo dnf search 关键词
```

### Arch（pacman）

```bash
sudo pacman -S nginx
sudo pacman -Rns nginx
```

> 装完先看服务有没有起来：`systemctl status nginx`。

---

## 9. 进程与系统状态

```bash
ps aux | grep nginx     # 查进程
top                     # 动态看 CPU/内存，q 退出
htop                    # 更好看（apt install htop）
kill 1234               # 结束 PID 1234
kill -9 1234            # 强杀（最后手段）
pkill -f "python app.py"  # 按命令行匹配结束
```

### systemd 服务

```bash
systemctl status nginx
sudo systemctl start nginx
sudo systemctl stop nginx
sudo systemctl restart nginx
sudo systemctl enable nginx     # 开机自启
systemctl list-units --type=service --state=running
```

### 日志

```bash
journalctl -u nginx -n 100      # 某服务最近 100 行
journalctl -u nginx -f          # 实时跟踪
journalctl --since "1 hour ago"
```

### 资源

```bash
df -h                   # 磁盘使用
du -sh *                # 当前目录各文件/目录大小
free -h                 # 内存
uname -a                # 内核信息
uptime                  # 运行时长、负载
```

---

## 10. 网络

```bash
ip a                    # 网卡与 IP
ip route                # 路由
ping -c 4 example.com   # 连通性
curl -I https://example.com   # 看响应头
curl -O https://example.com/file.tar.gz  # 下载
ss -tulpn               # 监听端口（替代 netstat）
```

### SSH 与传文件

```bash
ssh alice@192.168.1.10
ssh-keygen -t ed25519 -C "alice@example.com"
ssh-copy-id alice@192.168.1.10     # 免密登录
scp file.txt alice@host:/tmp/
rsync -avz ./site/ alice@host:/var/www/site/   # 增量同步
```

> 服务器安全组/防火墙要放行 22 端口；改 SSH 端口前先确认新端口可用，避免把自己关在门外。

### 防火墙（ufw，Ubuntu）

```bash
sudo ufw status
sudo ufw allow 22/tcp
sudo ufw allow 80,443/tcp
sudo ufw enable
```

---

## 11. 管道与文本处理

```bash
ls -l | less                     # 管道：前一个的输出给后一个
grep "error" app.log | wc -l     # 统计错误行数
command > out.txt                # 覆盖写入
command >> out.txt               # 追加
command 2> err.txt               # 只重定向错误
command > all.txt 2>&1           # 标准输出+错误一起
command | tee out.txt            # 屏幕显示同时写文件
```

### 三件套入门

```bash
cut -d: -f1 /etc/passwd          # 按冒号切，取第 1 列
sort file.txt | uniq -c | sort -nr   # 统计频次并倒序
sed -n '1,20p' file.txt          # 打印 1–20 行
sed -i 's/old/new/g' file.txt    # 原地替换
awk '{print $1, $3}' file.txt    # 打印第 1、3 列
awk -F: '$3>=1000 {print $1}' /etc/passwd   # 条件筛选
```

---

## 12. Shell 脚本

### 第一个脚本

```bash
#!/usr/bin/env bash
set -euo pipefail          # 出错即停、未定义变量报错、管道错误不吞

name="${1:-world}"
echo "hello, $name"
```

```bash
chmod +x hello.sh
./hello.sh 曦鲸
```

### 变量与判断

```bash
#!/usr/bin/env bash
set -euo pipefail

dir="/var/log"
if [ -d "$dir" ]; then
  echo "$dir 存在"
else
  echo "$dir 不存在"
fi

count=$(ls -1 "$dir" | wc -l)
echo "文件数：$count"
```

### 循环

```bash
for f in *.log; do
  echo "处理 $f"
  gzip "$f"
done

while read -r line; do
  echo "读到：$line"
done < list.txt
```

### 函数

```bash
log() {
  echo "[$(date '+%F %T')] $*"
}
log "开始备份"
```

### 定时任务

```bash
crontab -e
```

五个字段：分 时 日 月 周。

```cron
0 3 * * * /home/alice/backup.sh >> /home/alice/backup.log 2>&1
*/5 * * * * curl -s https://example.com/health > /dev/null
```

> 脚本里尽量用绝对路径；cron 的环境变量和交互式 shell 不一样。

---

## 13. 环境变量与配置

```bash
echo $PATH
export PATH="$PATH:/opt/bin"      # 当前会话有效
```

永久生效写进 `~/.bashrc`（bash）或 `~/.zshrc`（zsh）：

```bash
export EDITOR=vim
alias ll='ls -alF'
alias gs='git status'
```

改完执行 `source ~/.bashrc`。

---

## 14. 压缩与归档

```bash
tar -czf backup.tar.gz dir/       # 打包并 gzip
tar -xzf backup.tar.gz            # 解包
tar -tzf backup.tar.gz            # 只看内容
zip -r site.zip site/
unzip site.zip
```

---

## 15. 常见报错排查

| 现象 | 先查什么 |
| --- | --- |
| `command not found` | 是否安装；`echo $PATH`；拼写 |
| `Permission denied` | `ls -l` 权限/属主；是否需要 `sudo` |
| `No space left on device` | `df -h`、`du -sh /*` 找大文件 |
| 端口被占用 | `ss -tulpn \| grep 8080`，再 `kill` |
| 服务起不来 | `systemctl status xxx`、`journalctl -u xxx -n 50` |
| SSH 连不上 | 网络/安全组/`systemctl status ssh`/`ss -tulpn` |
| 改配置后不生效 | 是否 `restart`；配置路径；`nginx -t` 之类语法检查 |

---

## 16. 安全与好习惯

- 日常普通用户，`sudo` 按需使用。
- 重要文件定期备份，至少异地一份。
- 公网服务器：禁用密码登录、改用密钥；只开必要端口。
- 执行网上抄来的命令前，先读懂每一段，尤其是 `curl ... | bash`。
- 改配置前备份：`cp nginx.conf nginx.conf.bak`。
- 用 `history` 回顾操作，敏感命令注意别留在历史里。

---

## 17. 速查表

```bash
pwd ls cd mkdir cp mv rm            # 文件
cat less head tail grep             # 查看
chmod chown                         # 权限
find which                          # 查找
apt install / dnf install           # 装软件
ps top kill systemctl journalctl    # 进程与服务
df du free uname uptime             # 系统
ip ping curl ss ssh scp rsync       # 网络
tar zip unzip                       # 压缩
| > >> tee                          # 管道与重定向
```

---

## 18. 学习路线建议

1. 先用 WSL 或虚拟机把上面命令敲一遍，形成肌肉记忆。
2. 练习：用 `find` + `tar` 写一个按日期备份目录的脚本，配 `cron` 每天跑。
3. 学一点 `vim`（`:wq`、`i`、`Esc`、`/`）或 `nano`，服务器上总要改配置。
4. 再往下：用户/组、`systemd` 单元文件、`nginx` 反代、Docker、防火墙与日志分析。

> 教程里的命令以 Ubuntu 24.04 为基准；不同发行版把 `apt` 换成对应的包管理器即可。
