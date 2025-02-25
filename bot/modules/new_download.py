import time
from telebot import types
import subprocess
import sys
import threading
import re
from modules.creat_config import *


def get_free_space_mb():
    result=os.statvfs('/root/')
    block_size=result.f_frsize
    total_blocks=result.f_blocks
    free_blocks=result.f_bfree
    # giga=1024*1024*1024
    giga=1000*1000*1000
    total_size=total_blocks*block_size/giga
    free_size=free_blocks*block_size/giga
    print('total_size = %s' % int(total_size))
    print('free_size = %s' % free_size)
    return int(free_size)

def progessbar(new, tot):
    """Builds progressbar
    Args:
        new: current progress
        tot: total length of the download
    Returns:
        progressbar as a string of length 20
    """
    length = 20
    progress = int(round(length * new / float(tot)))
    percent = round(new/float(tot) * 100.0, 1)
    bar = '=' * progress + '-' * (length - progress)
    return '[%s] %s %s\r' % (bar, percent, '%')

def hum_convert(value):
    value=float(value)
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    size = 1024.0
    for i in range(len(units)):
        if (value / size) < 1:
            return "%.2f%s" % (value, units[i])
        value = value / size

def run_rclone(dir,title,info,file_num):

    Rclone_remote=os.environ.get('Remote')
    Upload=os.environ.get('Upload')

    name=f"{str(info.message_id)}_{str(info.chat.id)}"
    if int(file_num)==1:
        shell=f"rclone copy \"{dir}\" \"{Rclone_remote}:{Upload}\"  -v --stats-one-line --stats=1s --log-file=\"{name}.log\" "
    else:
        shell=f"rclone copy \"{dir}\" \"{Rclone_remote}:{Upload}/{title}\"  -v --stats-one-line --stats=1s --log-file=\"{name}.log\" "
    print(shell)
    cmd = subprocess.Popen(shell, stdin=subprocess.PIPE, stderr=sys.stderr, close_fds=True,
                           stdout=subprocess.PIPE, universal_newlines=True, shell=True, bufsize=1)
    # 实时输出
    temp_text=None
    while True:
        time.sleep(1)
        fname = f'{name}.log'
        with open(fname, 'r') as f:  #打开文件
            try:
                lines = f.readlines() #读取所有行

                for a in range(-1,-10,-1):
                    last_line = lines[a] #取最后一行
                    if last_line !="\n":
                        break

                print (f"上传中\n{last_line}")
                if temp_text != last_line and "ETA" in last_line:
                    log_time,file_part,upload_Progress,upload_speed,part_time=re.findall("(.*?)INFO.*?(\d.*?),.*?(\d+%),.*?(\d.*?s).*?ETA.*?(\d.*?)",last_line , re.S)[0]
                    text=f"{title}\n" \
                         f"更新时间：`{log_time}`\n" \
                         f"上传部分：`{file_part}`\n" \
                         f"上传进度：`{upload_Progress}`\n" \
                         f"上传速度：`{upload_speed}`\n" \
                         f"剩余时间:`{part_time}`"
                    bot.edit_message_text(text=text,chat_id=info.chat.id,message_id=info.message_id,parse_mode='Markdown')
                    temp_text = last_line
                f.close()

            except Exception as e:
                print(e)
                f.close()
                continue

        if subprocess.Popen.poll(cmd) == 0:  # 判断子进程是否结束
            print("上传结束")
            bot.send_message(text=f"{title}\n上传结束",chat_id=info.chat.id)
            os.remove(f"{name}.log")
            return

    return


def the_download(url,message):
    os.system("df -lh")
    try:
        download = aria2.add_magnet(url)
    except Exception as e:
        print(e)
        if (str(e).endswith("No URI to download.")):
            print("No link provided!")
            bot.send_message(chat_id=message.chat.id,text="No link provided!",parse_mode='Markdown')
            return None
    prevmessagemag = None
    info=bot.send_message(chat_id=message.chat.id,text="Downloading",parse_mode='Markdown')
    markupmeta = types.InlineKeyboardMarkup()

    markupmeta.add(types.InlineKeyboardButton(f"Remove", callback_data=f"Remove {download.gid}"))
    temp_text=""
    while download.is_active:
        try:
            download.update()
            print("Downloading metadata")
            if temp_text!="Downloading metadata":
                bot.edit_message_text(text="Downloading metadata",chat_id=info.chat.id,message_id=info.message_id,parse_mode='Markdown', reply_markup=markupmeta)
                temp_text="Downloading metadata"
            barop = progessbar(download.completed_length,download.total_length)

            updateText = f"Downloading \n" \
                         f"'{download.name}'\n" \
                         f"Progress : {hum_convert(download.completed_length)}/{hum_convert(download.total_length)} \n" \
                         f"Peers:{download.connections}\n" \
                         f"Speed {hum_convert(download.download_speed)}/s\n" \
                         f"{barop}\n" \
                         f"Free:{get_free_space_mb()}GB"
            if prevmessagemag != updateText:
                print(updateText)
                bot.edit_message_text(text=updateText,chat_id=info.chat.id,message_id=info.message_id,parse_mode='Markdown')
                prevmessagemag = updateText
            time.sleep(2)
        except:

            try:
                download.update()
            except Exception as e:
                if (str(e).endswith("is not found")):
                    print("Metadata Cancelled/Failed")
                    print("Metadata couldn't be downloaded")
                    if temp_text!="Metadata Cancelled/Failed":
                        bot.edit_message_text(text="Metadata Cancelled/Failed",chat_id=info.chat.id,message_id=info.message_id,parse_mode='Markdown')
                        temp_text="Metadata Cancelled/Failed"
                    return None
            time.sleep(2)


    time.sleep(2)
    match = str(download.followed_by_ids[0])
    downloads = aria2.get_downloads()
    currdownload = None
    for download in downloads:
        if download.gid == match:
            currdownload = download
            break
    print("Download complete")

    markup = types.InlineKeyboardMarkup()

    markup.add(types.InlineKeyboardButton(f"Resume", callback_data=f"Resume {currdownload.gid}"),
               types.InlineKeyboardButton(f"Pause", callback_data=f"Pause {currdownload.gid}"),
               types.InlineKeyboardButton(f"Remove", callback_data=f"Remove {currdownload.gid}"))

    bot.edit_message_text(text="Download complete",chat_id=info.chat.id,message_id=info.message_id,parse_mode='Markdown', reply_markup=markup)
    prevmessage = None

    while currdownload.is_active or not currdownload.is_complete:

        try:
            currdownload.update()
        except Exception as e:
            if (str(e).endswith("is not found")):
                print("Magnet Deleted")
                print("Magnet download was removed")
                bot.edit_message_text(text="Magnet download was removed",chat_id=info.chat.id,message_id=info.message_id,parse_mode='Markdown')
                break
            print(e)
            print("Issue in downloading!")

        if currdownload.status == 'removed':
            print("Magnet was cancelled")
            print("Magnet download was cancelled")
            bot.edit_message_text(text="Magnet download was cancelled",chat_id=info.chat.id,message_id=info.message_id,parse_mode='Markdown')
            break

        if currdownload.status == 'error':
            print("Mirror had an error")
            currdownload.remove(force=True, files=True)
            print("Magnet failed to resume/download!\nRun /cancel once and try again.")
            bot.edit_message_text(text="Magnet failed to resume/download!\nRun /cancel once and try again.",chat_id=info.chat.id,message_id=info.message_id,parse_mode='Markdown', reply_markup=markup)
            break

        print(f"Magnet Status? {currdownload.status}")

        if currdownload.status == "active":
            try:
                currdownload.update()
                barop = progessbar(currdownload.completed_length,currdownload.total_length)

                updateText = f"Downloading \n" \
                             f"'{currdownload.name}'\n" \
                             f"Progress : {hum_convert(currdownload.completed_length)}/{hum_convert(currdownload.total_length)} \n" \
                             f"Peers:{currdownload.connections}\n" \
                             f"Speed {hum_convert(currdownload.download_speed)}/s\n" \
                             f"{barop}\n" \
                             f"Free:{get_free_space_mb()}GB"

                if prevmessage != updateText:
                    print(f"更新状态\n{updateText}")
                    bot.edit_message_text(text=updateText,chat_id=info.chat.id,message_id=info.message_id,parse_mode='Markdown', reply_markup=markup)
                    prevmessage = updateText
                time.sleep(2)
            except Exception as e:
                if (str(e).endswith("is not found")):
                    break
                print(e)
                print("Issue in downloading!")
                time.sleep(2)
        elif currdownload.status == "paused":
            try:
                currdownload.update()
                barop = progessbar(currdownload.completed_length,currdownload.total_length)

                updateText = f"Downloading \n" \
                             f"'{currdownload.name}'\n" \
                             f"Progress : {hum_convert(currdownload.completed_length)}/{hum_convert(currdownload.total_length)} \n" \
                             f"Peers:{currdownload.connections}\n" \
                             f"Speed {hum_convert(currdownload.download_speed)}/s\n" \
                             f"{barop}\n" \
                             f"Free:{get_free_space_mb()}GB"

                if prevmessage != updateText:
                    print(f"更新状态\n{updateText}")
                    bot.edit_message_text(text=updateText,chat_id=info.chat.id,message_id=info.message_id,parse_mode='Markdown', reply_markup=markup)
                    prevmessage = updateText
                time.sleep(2)
            except Exception as e:
                print(e)
                print("Download Paused Flood")
                time.sleep(2)
        time.sleep(2)

        time.sleep(1)

    if currdownload.is_complete:
        print(currdownload.name)
        try:
            print("开始上传")
            file_dir=f"{currdownload.dir}/{currdownload.name}"
            files_num=int(len(currdownload.files))
            run_rclone(file_dir,currdownload.name,info=info,file_num=files_num)
            currdownload.remove(force=True,files=True)

        except Exception as e:
            print(e)
            print("Upload Issue!")
    return None

def http_download(url,message):
    try:
        currdownload = aria2.add_uris([url])
    except Exception as e:
        print(e)
        if (str(e).endswith("No URI to download.")):
            print("No link provided!")
            bot.send_message(chat_id=message.chat.id,text="No link provided!",parse_mode='Markdown')
            return None

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(f"Resume", callback_data=f"Resume {currdownload.gid}"),
               types.InlineKeyboardButton(f"Pause", callback_data=f"Pause {currdownload.gid}"),
               types.InlineKeyboardButton(f"Remove", callback_data=f"Remove {currdownload.gid}"))
    info=bot.send_message(chat_id=message.chat.id,text="Downloading",parse_mode='Markdown')
    prevmessage=None
    while currdownload.is_active or not currdownload.is_complete:

        try:
            currdownload.update()
        except Exception as e:
            if (str(e).endswith("is not found")):
                print("url Deleted")
                print("url download was removed")
                bot.edit_message_text(text="url download was removed",chat_id=info.chat.id,message_id=info.message_id,parse_mode='Markdown')
                break
            print(e)
            print("url in downloading!")

        if currdownload.status == 'removed':
            print("url was cancelled")
            print("url download was cancelled")
            bot.edit_message_text(text="Magnet download was cancelled",chat_id=info.chat.id,message_id=info.message_id,parse_mode='Markdown')
            break

        if currdownload.status == 'error':
            print("url had an error")
            currdownload.remove(force=True, files=True)
            print("url failed to resume/download!.")
            bot.edit_message_text(text="Magnet failed to resume/download!\nRun /cancel once and try again.",chat_id=info.chat.id,message_id=info.message_id,parse_mode='Markdown', reply_markup=markup)
            break

        print(f"url Status? {currdownload.status}")

        if currdownload.status == "active":
            try:
                currdownload.update()
                barop = progessbar(currdownload.completed_length,currdownload.total_length)

                updateText = f"Downloading \n" \
                             f"'{currdownload.name}'\n" \
                             f"Progress : {hum_convert(currdownload.completed_length)}/{hum_convert(currdownload.total_length)} \n" \
                             f"Speed {hum_convert(currdownload.download_speed)}/s\n" \
                             f"{barop}\n" \
                             f"Free:{get_free_space_mb()}GB"

                if prevmessage != updateText:
                    print(f"更新状态\n{updateText}")
                    bot.edit_message_text(text=updateText,chat_id=info.chat.id,message_id=info.message_id,parse_mode='Markdown', reply_markup=markup)
                    prevmessage = updateText
                time.sleep(2)
            except Exception as e:
                if (str(e).endswith("is not found")):
                    break
                print(e)
                print("Issue in downloading!")
                time.sleep(2)
        elif currdownload.status == "paused":
            try:
                currdownload.update()
                barop = progessbar(currdownload.completed_length,currdownload.total_length)

                updateText = f"Downloading \n" \
                             f"'{currdownload.name}'\n" \
                             f"Progress : {hum_convert(currdownload.completed_length)}/{hum_convert(currdownload.total_length)} \n" \
                             f"Speed {hum_convert(currdownload.download_speed)}/s\n" \
                             f"{barop}\n" \
                             f"Free:{get_free_space_mb()}GB"

                if prevmessage != updateText:
                    print(f"更新状态\n{updateText}")
                    bot.edit_message_text(text=updateText,chat_id=info.chat.id,message_id=info.message_id,parse_mode='Markdown', reply_markup=markup)
                    prevmessage = updateText
                time.sleep(2)
            except Exception as e:
                print(e)
                print("Download Paused Flood")
                time.sleep(2)
        time.sleep(2)

        time.sleep(1)
    if currdownload.is_complete:
        print(currdownload.name)
        try:
            print("开始上传")
            file_dir=f"{currdownload.dir}/{currdownload.name}"
            run_rclone(file_dir,currdownload.name,info=info,file_num=1)
            currdownload.remove(force=True,files=True)

        except Exception as e:
            print(e)
            print("Upload Issue!")
    return None


@bot.message_handler(commands=['magnet'],func=lambda message:str(message.chat.id) == str(Telegram_user_id))
def start_download(message):
    try:
        keywords = str(message.text)
        if str(BOT_name) in keywords:
            keywords = keywords.replace(f"/magnet@{BOT_name} ", "")
            print(keywords)
            t1 = threading.Thread(target=the_download, args=(keywords,message))
            t1.start()
        else:
            keywords = keywords.replace(f"/magnet ", "")
            print(keywords)
            t1 = threading.Thread(target=the_download, args=(keywords,message))
            t1.start()

    except Exception as e:
        print(f"magnet :{e}")

@bot.message_handler(commands=['mirror'],func=lambda message:str(message.chat.id) == str(Telegram_user_id))
def start_http_download(message):
    try:
        keywords = str(message.text)
        if str(BOT_name) in keywords:
            keywords = keywords.replace(f"/mirror@{BOT_name} ", "")
            print(keywords)
            t1 = threading.Thread(target=http_download, args=(keywords,message))
            t1.start()
        else:
            keywords = keywords.replace(f"/mirror ", "")
            print(keywords)
            t1 = threading.Thread(target=http_download, args=(keywords,message))
            t1.start()

    except Exception as e:
        print(f"start_http_download :{e}")


@bot.message_handler(commands=['magfile'])
def send_telegram_file(message):
    bot.send_message(chat_id=message.chat.id, text="请发送文件,或输入 /cancel 取消",parse_mode="MarkdownV2")
    bot.register_next_step_handler(message, get_telegram_file)

def get_telegram_file(message):
    print(message)

    if message.text=="/cancel":
        bot.send_message(chat_id=message.chat.id, text="已退出搜图模式", parse_mode="MarkdownV2")
        return
    if message.content_type!="document":
        bot.send_message(chat_id=message.chat.id, text="请发送文件,或输入 /cancel 取消",parse_mode="MarkdownV2")

        bot.register_next_step_handler(message,get_telegram_file)
        return
    else:
        #url = bot.get_file_url(message.document.file_id)
        file_url=bot.get_file_url(file_id=message.document.file_id)
        print(file_url)
        t1 = threading.Thread(target=the_download, args=(file_url,message))
        t1.start()


        #bot.send_message(chat_id=message.chat.id, text="搜索完成", parse_mode="MarkdownV2")


