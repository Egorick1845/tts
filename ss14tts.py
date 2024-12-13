import base64, os, io, sys

import re
from russtress import Accent

from src.SpeakerPatch import SpeakerPatch,SpeakerPatchInit
from src.WarmUp import WarmUp
from src.SoundEffects import add_echo, add_radio_effect

import torch
import torchaudio

# ffmpeg fix
current_directory = os.path.abspath(os.path.dirname(__file__))
bin_directory = os.path.join(current_directory, 'bin')
os.environ['PATH'] = f"{bin_directory}:{os.environ['PATH']}"
sys.path.append(bin_directory)

accent = Accent()

print(torchaudio.list_audio_backends())

torch.set_num_threads(int(os.environ.get("threads","6")))
torchaudio.set_audio_backend("sox")

language = 'ru'
model_id = 'v3_1_ru'
deviceName = "cuda" if torch.cuda.is_available() else "cpu"
device = torch.device(deviceName)

ApiToken = os.environ.get("apitoken","test")

local_file = 'model.pt'
if not os.path.isfile(local_file):
    print("Start download silero models")
    torch.hub.download_url_to_file('https://models.silero.ai/models/tts/ru/v3_1_ru.pt',
                                   local_file)  

model = torch.package.PackageImporter(local_file).load_pickle("tts_models", "model")
example_text = "В недрах тундры выдры в г+етрах т+ырят в вёдра ядра кедров."
#model, example_text = torch.hub.load(repo_or_dir='snakers4/silero-models',
#    model='silero_tts',
#    language=language,
#    speaker=model_id, 
#    trust_repo=True,
#    verbose=False
#)

model.to(device)  # gpu or cpu

from flask import Flask, request, jsonify, abort

app = Flask(__name__)

#import logging
#log = logging.getLogger('werkzeug')
#log.setLevel(logging.ERROR)
#app.logger.disabled = True
#log.disabled = True


# доступные спикера
speakers = model.speakers # ['aidar', 'baya', 'kseniya', 'xenia', 'eugene', 'random']

SpeakerPatchInit(model,example_text)

# Docker HealthCheck
@app.route('/health', methods=['GET'])
def doHEALTH():
    return "OK"

# TTS вход
@app.route('/tts', methods=['POST'])
def doTTS():
    req = request.json
    if req['api_token'] != ApiToken:
        abort(403)
        return
    if 'text' not in req:
        abort(400)
        return
    if 'speaker' not in req:
        abort(400)
        return
    audio = None
    speaker = req['speaker']

    if 'sample_rate' not in req:
        req['sample_rate'] = 24000
    if 'put_accent' not in req:
        req['put_accent'] = True
    if 'put_yo' not in req:
        req['put_yo'] = False
    if 'format' not in req:
        req['format'] = 'ogg'

    speaker, voiceFile = SpeakerPatch(speaker,speakers)

    if 'ssml' in req and req['ssml']:
        audio = model.apply_tts(ssml_text=patch_ssml(req['text']),
            speaker=speaker,
            sample_rate=req['sample_rate'],
            put_accent=req['put_accent'],
            put_yo=req['put_yo'],
            voice_path=voiceFile
        )
    else:
        audio = model.apply_tts(text=patch_text(req['text']),
            speaker=speaker,
            sample_rate=req['sample_rate'],
            put_accent=req['put_accent'],
            put_yo=req['put_yo'],
            voice_path=voiceFile
        )
    # Saving to bytes buffer
    buffer_ = io.BytesIO()
    torchaudio.save(buffer_, audio.unsqueeze(0), req['sample_rate'], format=req["format"])
    buffer_.seek(0)

    effect = None
    if 'effect' in req:
        effect = req['effect']

    if effect == "Echo": 
        buffer_ = add_echo(buffer_, output_format=req["format"])
    elif effect == "Radio":
        buffer_ = add_radio_effect(buffer_, req['sample_rate'], format=req["format"])

    return jsonify({'results': [{'audio': base64.b64encode(buffer_.getvalue()).decode()}]})

def patch_ssml(ssml_content):
    def add_accents(match):
        text = match.group(1)
        try:
            accented_text = accent.put_stress(text)
        except:
            accented_text = text  # Если не удалось поставить ударение, возвращаем исходный текст
        return f">{accented_text}<"

    # Заменяем текст внутри тегов
    patched_ssml = re.sub(r'>([^<>]+)<', add_accents, ssml_content)
    return patched_ssml

def patch_text(text_content):
    text = ""
    try:
        text = accent.put_stress(text_content)
    except:
        text = text_content  # Если не удалось поставить ударение, возвращаем исходный текст
    return text

if __name__ == '__main__':
    WarmUp(model,speakers)
    app.run(host= '0.0.0.0',debug=False,port=int(os.environ.get("PORT","5000")))
