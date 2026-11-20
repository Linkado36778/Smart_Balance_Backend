import requests

with open(r'W:/Imagens/Prints/LazaroSecretaria/Agendamento de entrevistas.png', 'rb') as f:
    data = {'category': 'frutas',
            'file': f}
    r = requests.post('http://localhost:8000/upload-image', data=data, timeout=10)
    print(r.json())
