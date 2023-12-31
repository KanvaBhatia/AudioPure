import gradio as gr

import torch
from torchaudio.backend.common import AudioMetaData
from df.enhance import enhance, load_audio, save_audio
from df.io import resample
from libdf import DF
from df.model import ModelParams
from df import config
import moviepy.editor as mp
import numpy as np

try:
    config.load('config.ini')
except Exception as e:
    print(e)
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

p = ModelParams()
df = DF(
    sr=p.sr,
    fft_size=p.fft_size,
    hop_size=p.hop_size,
    nb_bands=p.nb_erb,
    min_nb_erb_freqs=p.min_nb_freqs,
)


print("Device - ", DEVICE)
model = torch.load(("model.pth"), map_location=torch.device('cpu'))
model.to(DEVICE)
model.eval()

def identity(video_path):
    print(video_path)
    # audio = mp.AudioFileClip(x)
    # wav_file = x
    # audio.write_audiofile(wav_file)
    video = mp.VideoFileClip(video_path)
    audio = video.audio
    wav_file = "tmp.wav"
    audio.write_audiofile(wav_file)
    print("Wav stored.")
    meta = AudioMetaData(-1, -1, -1, -1, "")
    sr = config("sr", 48000, int, section="df")
    sample, meta = load_audio(wav_file, sr)
    len_audio = (meta.num_frames/meta.sample_rate)/60
    max_min = 1
    if len_audio  % max_min < 0.1:
        num_chunks = len_audio // max_min
    else:
        num_chunks = len_audio // max_min + 1
    print(f"Total length of audio = {len_audio} chunks = {num_chunks}")
    estimate = []
    split_tensors = torch.tensor_split(sample, int(num_chunks), dim = 1)
    for i in range(len(split_tensors)):
        enhanced = enhance(model, df, split_tensors[i])
        enhanced = enhance(model, df, enhanced)
        lim = torch.linspace(0.0, 1.0, int(sr * 0.15)).unsqueeze(0)
        lim = torch.cat((lim, torch.ones(1, enhanced.shape[1] - lim.shape[1])), dim=1)
        enhanced = enhanced * lim
        enhanced = resample(enhanced, sr, meta.sample_rate)
        estimate.append(enhanced)
    estimate = tuple(estimate)
    enhanced = torch.cat(estimate, dim = -1)
    sr = meta.sample_rate
    save_audio("enhanced_aud.wav", enhanced, sr)
    audio = mp.AudioFileClip('enhanced_aud.wav')
    video = mp.VideoFileClip(video_path)
    final_video = video.set_audio(audio)
    final_video.write_videofile("output_video.mp4", 
            codec='libx264', 
            audio_codec='aac', 
            temp_audiofile='temp-audio.m4a', 
            remove_temp=True
            )
    return "output_video.mp4"

demo = gr.Interface(
    fn=identity,
    title="Audio Denoiser using DeepFilterNet V3",
    description="Implemented audio denoising using DeepFilterNet V3, enabled processing of larger files even on cpu, by splitting up the audio file into chunks of 1 minute each.",
    inputs=gr.Video(label="Input Video", sources="upload"),
    outputs=gr.Video(label="Output Video"),
)
demo.launch(share=True, debug=True)
