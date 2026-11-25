import os
import requests

r = requests.post(
    "https://api.sendgrid.com/v3/mail/send",
    headers={"Authorization": "Bearer " + os.environ["SENDGRID_API_KEY"]},
    json={
        "personalizations": [{"to": [{"email": "ea.gamezg.2528@cbtis198.edu.mx"}]}],
        "from": {"email": "trelliot27@gmail.com"},
        "subject": "Prueba SendGrid",
        "content": [{"type": "text/plain", "value": "Si lees esto, SendGrid funciona."}],
    },
)
print(r.status_code, r.text)