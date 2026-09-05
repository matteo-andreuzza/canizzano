# Il braccio operativo della dashboard: l'unico container che puo' pilotare
# Docker sull'host. Django gli passa i lavori scrivendo un file nella coda,
# lui esegue canizzano.sh e scrive l'esito nel registro delle attivita'.
#
# Perche' non lo fa Django direttamente: il container del CMS non ha ne' lo
# script ne' la CLI di Docker, e soprattutto «avvia» e «tutto» ricreano il
# container del backend — cioe' ucciderebbero il processo che sta servendo la
# richiesta. Qui invece siamo in un container separato, che nessun comando
# della dashboard tocca: sopravvive al riavvio del CMS e puo' raccontare com'e'
# andata a cose fatte.
FROM docker:cli

# bash:   canizzano.sh usa array e «<<<», che la sh di Alpine non conosce.
# python3: serve a scrivere JSON con le virgolette al posto giusto.
# tzdata:  senza, Alpine ignora TZ e registra tutto in UTC — nel registro
#          condiviso comparirebbero due fusi diversi per lo stesso momento.
RUN apk add --no-cache bash python3 tzdata

COPY esecutore.py /usr/local/bin/esecutore.py

# Niente CMD in forma shell: cosi' i segnali di «docker stop» arrivano al
# processo Python e il ciclo puo' chiudersi in modo pulito.
CMD ["python3", "-u", "/usr/local/bin/esecutore.py"]
