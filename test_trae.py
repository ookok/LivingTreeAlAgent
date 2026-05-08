import urllib.request, json

token = 'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7ImlkIjoiNTIwNTM4MzE2ODY4NjQ3Iiwic291cmNlIjoicmVmcmVzaF90b2tlbiIsInNvdXJjZV9pZCI6InU5dFdzX2pBajdWOHNiZHFXLUI4a0tyX1l5b1ZTekhuM09GZ0t5WDFOTXc9LjE4YWQ4NTk5NDJkMDQyNmQiLCJ0ZW5hbnRfaWQiOiI3bzJkODk0cDdkcjBvNCIsInR5cGUiOiJ1c2VyIn0sImV4cCI6MTc3OTQzMzkyMSwiaWF0IjoxNzc4MjI0MzIxfQ.MRG2ZLMmsbmDjjtXZ3rOl3Sg4E4c1OyVdAMqmy6oQjV5-q6SZLenCUqQAfE920sgeb-vTQD-T3LN0sAHVFi_z3ys3Eo2J3d2_Wq1k04y7yI6kH0blPrOA_4vFTXP5bqu-pH9Jcb5dK03y7mjmSBm6fbRDKVYP-nwKNwoboX38errxq7qvMQHBKRs0vmmd1UFXUxWH16EBUJ2QRW3PCDanggMFwr2eJdauj23SvcALNjQykChCakJgHCkaLrxkGPyw8AvDgj7mAXaK53zRNatU5W6QkW2wIZa2tSqHsfcR_rHDWXqW4QJG2FNLM3jQn0HAOFkHeaZqn0B5QPrvPvKSnGqZwmuo1N8I2OAqnx5RtcYQx4ENj20Dm-YX1rJCQMsvZJkpEhqwKNxdFX6zw2a8bQLTvf1Desi6Zj_g4itHSgVUH3qgQk3M60SNJEvhYIpnQSA9JM_AECYGqKNa_C0PYf8Z_U0P_86JeXDYFAJMZYNvHoX4lhPNMms-5iOT1g5hSGMOFpO0wlIYBy552Ube12NC537vdr96fWWRkZoE1kcf9f8BlDIgRDLGA0qHDsIa0LFWZdOCUD0ajx6qNNbKN-NNf7jgyzMV3ctxz2sRKwiyYOiwPE5CMVb8CTHJqbZgn6Tl4nNPjDb6VtMtw4pRWqNP_v8glgtNiudVPm6wTc'

# Try different API paths
paths = [
    'https://api.trae.com.cn/models',
    'https://api.trae.com.cn/v1/models',
    'https://api.trae.com.cn/api/v1/models',
    'https://api.trae.com.cn/api/models',
    'http://127.0.0.1:55915/v1/models',
    'http://127.0.0.1:55915/models',
]

for path in paths:
    try:
        r = urllib.request.urlopen(urllib.request.Request(
            path, headers={'Authorization': f'Bearer {token}'}
        ), timeout=5)
        data = json.loads(r.read())
        print(f'{path}: OK')
    except Exception as e:
        print(f'{path}: {str(e)[:80]}')
