import shutil
import subprocess
from typing import Iterator, Union


def is_installed(lib_name: str) -> bool:
    lib = shutil.which(lib_name)
    if lib is None:
        return False
    return True


def play(
    audio: Union[bytes, Iterator[bytes]], 
    notebook: bool = False, 
    use_ffmpeg: bool = True
) -> None:
    # Convert iterator to bytes if needed
    audio_bytes: bytes = b"".join(audio) if isinstance(audio, Iterator) else audio
    
    if notebook:
        try:
            from IPython.display import Audio, display  # type: ignore
        except ModuleNotFoundError:
            raise ValueError(
                "`pip install ipython` required when `notebook=True` "
            )

        display(Audio(audio_bytes, rate=44100, autoplay=True))
    elif use_ffmpeg:
        if not is_installed("ffplay"):
            raise ValueError(
                "ffplay from ffmpeg not found, necessary to play audio. "
                "On Mac: 'brew install ffmpeg'. "
                "On Linux/Windows: https://ffmpeg.org/"
            )
        args = ["ffplay", "-autoexit", "-", "-nodisp"]
        proc = subprocess.Popen(
            args=args,
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out, err = proc.communicate(input=audio_bytes)
        proc.poll()
    else:
        try:
            import io
            import sounddevice as sd  # type: ignore
            import soundfile as sf  # type: ignore
        except ModuleNotFoundError:
            raise ValueError(
                "`pip install sounddevice soundfile` required when `use_ffmpeg=False` "
            )
        sd.play(*sf.read(io.BytesIO(audio_bytes)))
        sd.wait()


def save(audio: Union[bytes, Iterator[bytes]], filename: str) -> None:
    if isinstance(audio, Iterator):
        audio = b"".join(audio)
    with open(filename, "wb") as f:
        f.write(audio)


def stream(audio_stream: Iterator[bytes]) -> bytes:
    if not is_installed("mpv"):
        message = (
            "mpv not found, necessary to stream audio. "
            "On mac you can install it with 'brew install mpv'. "
            "On linux and windows you can install it from https://mpv.io/"
        )
        raise ValueError(message)

    mpv_command = ["mpv", "--no-cache", "--no-terminal", "--", "fd://0"]
    mpv_process = subprocess.Popen(
        mpv_command,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    audio = b""

    for chunk in audio_stream:
        if chunk is not None:
            mpv_process.stdin.write(chunk)  # type: ignore
            mpv_process.stdin.flush()  # type: ignore
            audio += chunk
    if mpv_process.stdin:
        mpv_process.stdin.close()
    mpv_process.wait()

    return audio
