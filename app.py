from re import I
import gradio as gr
from numba import none
import whisper
import torch
import os
import subprocess
import tempfile
from vr import AudioPre
from vr import AudioPre


def format_time(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = seconds % 60  # 保留小数部分
    return f"{hours:02}:{minutes:02}:{seconds:06.3f}".replace('.', ',')  # 保留两位小数并替换小数点为逗号
def generate_srt(result):
    srt_output = ""
    for i, segment in enumerate(result['segments']):
        words = segment.get('words', [])
        if not words:
            continue
        print(segment)
        start_time = format_time(segment["words"][0]["start"])
        end_time = format_time(segment["words"][-1]["end"])
        text = segment["text"]
        
        # SRT 格式
        srt_output += f"{i + 1}\n"  # 字幕序号
        srt_output += f"{start_time} --> {end_time}\n"  # 时间戳
        srt_output += f"{text}\n\n"  # 字幕文本

    print(srt_output)
    return srt_output

def recognize_audio(audio_path):
    # 在这里加载模型
    
    device = torch.device("cuda" if torch.cuda.is_available() else "xpu" if torch.xpu.is_available() else "cpu")
    model = whisper.load_model("large-v3", download_root="./", device=device)
    result = model.transcribe(audio_path, initial_prompt="将结果转录为简体中文", word_timestamps=True)
    return generate_srt(result)

def download_video(video_upload,url):
    if video_upload is None and url is None:
        yield "请上传视频或输入视频链接地址",None,None,None,None
        return
    mp4_path = None
    if video_upload is not None:
        mp4_path = video_upload
    else:
        yield "正在下载视频...",None,None,None,None
        cmd = 'python -m pip install --upgrade yt-dlp'
        subprocess.run(cmd, shell=True)
        tmp_path = tempfile.gettempdir()+'/gradio'
        out_tmpl = os.path.join(tmp_path, "voicetosrt_%(id)s.%(ext)s")
        cmd = (
            f'python -m yt_dlp --windows-filenames --buffer-size 4k '
            f'--merge-output-format mp4 -f "bv*+ba/b" '
            f'--print after_move:filepath -o "{out_tmpl}" "{url}"'
        )
        yield "正在下载视频...",None,None,None,None
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if proc.returncode != 0:
            yield "yt-dlp 下载失败",None,None,None,None
            raise RuntimeError(proc.stderr or proc.stdout or "yt-dlp 下载失败")
        

        lines = [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]
        mp4_path = next((ln for ln in reversed(lines) if ln.lower().endswith(".mp4")), lines[-1] if lines else "")
    
        if not mp4_path or not os.path.exists(mp4_path):
            raise RuntimeError(f"未找到下载后的 mp4 文件路径。stdout={proc.stdout!r}")
    yield "正在转换音频格式...",mp4_path,None,None,None
    audio_path = os.path.join(os.path.dirname(mp4_path), os.path.basename(mp4_path).replace(".mp4", ".wav"))
    cmd = f'ffmpeg -i "{mp4_path}" -ar 16000 -ac 1 -c:a pcm_s16le -y "{audio_path}"'
    subprocess.run(cmd, shell=True)


    audio_path_mp3=os.path.join(os.path.dirname(mp4_path), os.path.basename(mp4_path).replace(".mp4", ".mp3"))
    cmd = f'ffmpeg -i "{audio_path}"  -y "{audio_path_mp3}"'
    subprocess.run(cmd, shell=True)
    yield "正在分离人声和伴奏...",mp4_path,audio_path_mp3,None,None
    # UVR5(libv5) 分离：vr.AudioPre 里 ins_root/vocal_root 需要是“目录”，不是文件路径
    agg = 10
    sep_dir = os.path.dirname(audio_path)
    device = torch.device("cuda" if torch.cuda.is_available() else "xpu" if torch.xpu.is_available() else "cpu")
    extract_model = AudioPre(
        agg=agg,
        model_path="./HP5_only_main_vocal.pth",  # 模型权重文件路径
        device=device,
        is_half=False,
    )
    extract_model._path_audio_(
        music_file=audio_path,  # 必须是音频文件路径，不要传目录
        ins_root=sep_dir,
        vocal_root=sep_dir,
        format="mp3",
    )

    name = os.path.basename(audio_path)
    instrumental_audio_path = os.path.join(sep_dir, f"instrument_{name}_10.mp3")
    vocal_audio_path = os.path.join(sep_dir, f"vocal_{name}_10.mp3")
    yield "处理完成",mp4_path, audio_path_mp3, vocal_audio_path, instrumental_audio_path

def use_vocal_audio_func(vocal_audio_download):
    return vocal_audio_download

with gr.Blocks(css=".divider-line hr {height: 5px; background: linear-gradient(to right, #ff0000, #0000ff); border: none; margin: 20px 0;}") as demo:
    gr.Markdown("# 第一步、视频下载")
    with gr.Row():
        with gr.Column():
            with gr.TabItem("视频上传"):
                video_upload=gr.Video(label="上传视频")
                
            with gr.TabItem("视频下载"):
                with gr.Column():
                    gr.Markdown("## 输入视频链接地址")
                    video_url = gr.Textbox(label="输入视频链接地址",value="https://www.bilibili.com/video/BV1Y3TTzCETb")   
                #with gr.Column():
            gr.Markdown("## 下载结果")
            btn_download = gr.Button("下载并处理视频（云端禁止访问其他网站，请下载工程部署在自己电脑上）",variant="primary")
            video_download = gr.Video(label="下载结果")
            
        with gr.Column():
            progress_download = gr.Textbox(label="处理进度",interactive=False)
            audio_download = gr.Audio(label="视频转音频",show_download_button=True)
            vocal_audio_download=gr.Audio(label="人声音频",interactive=False,show_download_button=True)
            instrumental_audio_download=gr.Audio(label="伴奏音频",interactive=False,show_download_button=True)

    btn_download.click(fn=download_video, inputs=[video_upload,video_url], outputs=[progress_download,video_download,audio_download,vocal_audio_download,instrumental_audio_download])
    examples = [
        "example/1.mp4"
    ]
    gr.Examples(examples, video_upload,outputs=[progress_download,video_download,audio_download,vocal_audio_download,instrumental_audio_download])
                
    gr.Markdown("--------------------------------",elem_classes="divider-line")
    gr.Markdown("# 第二步、音频转录成字幕")
    with gr.Row():
        with gr.Column():
            gr.Markdown("请上传音频文件或使用第一步生成的人声音频。")
            use_vocal_audio=gr.Button("使用第一步生成的人声音频",variant="primary")
            audio_upload = gr.Audio(label="上传音频文件", type="filepath")
            use_vocal_audio.click(fn=use_vocal_audio_func, inputs=vocal_audio_download, outputs=audio_upload)
            
        btn_transcribe = gr.Button("转录")
        with gr.Column():
            gr.Markdown("## 转录结果")
            outputs = gr.TextArea(label="转录结果",show_copy_button=True)
    
    btn_transcribe.click(fn=recognize_audio, inputs=audio_upload, outputs=outputs)
    examples = [
        "example/asr_example.wav",
        "example/ceshi.wav",
        "example/dehua_zh.wav",
        "example/yuchengdong_zh.wav",
    ]
    gr.Examples(examples, audio_upload, outputs)



# 启动服务
if __name__ == "__main__":
    # inbrowser=True：服务就绪后自动用系统默认浏览器打开页面
    demo.launch(inbrowser=True)