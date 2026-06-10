"""
政策信息监控工具 - 一键启动器
双击运行后：
1. 启动 Flask 服务（后台，无控制台窗口）
2. 等待服务就绪
3. 自动打开浏览器
"""
import os
import sys
import time
import subprocess
import webbrowser
import socket


def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0


def show_error(msg):
    import ctypes
    ctypes.windll.user32.MessageBoxW(0, msg, "启动失败", 0x10)


def main():
    # 确定基础路径：打包后取 EXE 所在目录，开发态取脚本所在目录
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    # 优先使用 pythonw.exe（无窗口），回退到 python.exe
    python_exe = os.path.join(base_dir, 'python', 'pythonw.exe')
    if not os.path.exists(python_exe):
        python_exe = os.path.join(base_dir, 'python', 'python.exe')

    app_py = os.path.join(base_dir, 'app.py')

    if not os.path.exists(python_exe):
        show_error("找不到嵌入式 Python（python\\pythonw.exe 或 python\\python.exe）\n"
                   "请确保本程序放在项目根目录下")
        return

    if not os.path.exists(app_py):
        show_error("找不到 app.py\n请确保本程序放在项目根目录下")
        return

    # 端口已占用：可能服务已在运行，直接打开浏览器
    if is_port_in_use(5000):
        webbrowser.open('http://127.0.0.1:5000')
        return

    # 设置环境变量
    env = os.environ.copy()
    env['PLAYWRIGHT_BROWSERS_PATH'] = '0'

    # 启动 Flask 服务（后台，无窗口）
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0  # SW_HIDE

    creationflags = 0
    if hasattr(subprocess, 'CREATE_NO_WINDOW'):
        creationflags |= subprocess.CREATE_NO_WINDOW
    if hasattr(subprocess, 'DETACHED_PROCESS'):
        creationflags |= subprocess.DETACHED_PROCESS

    try:
        subprocess.Popen(
            [python_exe, app_py],
            cwd=base_dir,
            env=env,
            startupinfo=startupinfo,
            creationflags=creationflags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            close_fds=True,
        )
    except Exception as e:
        show_error(f"启动 Flask 进程失败：{e}")
        return

    # 等待服务启动（最多 15 秒）
    started = False
    for _ in range(30):
        if is_port_in_use(5000):
            started = True
            break
        time.sleep(0.5)

    if not started:
        show_error("服务启动超时，请检查日志 logs/app.log")
        return

    # 打开浏览器
    webbrowser.open('http://127.0.0.1:5000')


if __name__ == '__main__':
    main()
