FROM pytorch/pytorch:1.13.1-cuda11.6-cudnn8-runtime
ENV AM_I_IN_A_DOCKER_CONTAINER Yes
ENV language ru
ENV model_id v3_1_ru
ENV speakers aidar,baya,kseniya,xenia,eugene,random
VOLUME [ "/root/.cache/" ]
VOLUME [ "/workspace/voices" ]
VOLUME [ "/config" ]
RUN python -m venv venv
RUN . venv/bin/activate
ADD requirements.txt .
RUN pip3 install -r ./requirements.txt --extra-index-url https://download.pytorch.org/whl/cu116
RUN yes | pip3 uninstall torchaudio
RUN pip3 install soundfile torchaudio --extra-index-url https://download.pytorch.org/whl/cu116
ADD ss14tts.py .
ADD wsgi.py .
COPY src src/
HEALTHCHECK CMD curl -f http://localhost/
RUN pip3 install gevent
RUN python -c "from ss14tts import app"
EXPOSE 5000
ENTRYPOINT [ "python", "wsgi.py" ]