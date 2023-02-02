import json
import openai
import boto3

client = boto3.client("secretsmanager")
secretsmanagerAnswer = client.get_secret_value(SecretId="ChatGPT_API_Key")['SecretString']
openAIAPiKey = None
try:
    jsonData = json.loads(secretsmanagerAnswer)
    openAIAPiKey = jsonData['ChatGPT_API_Key']
except Exception as e:
    openAIAPiKey = secretsmanagerAnswer

openai.api_key = openAIAPiKey


def lambda_handler(event, context):
    print(event)
    # Passing the message to OpenAI
    query = openai.Completion.create(
        model="text-davinci-003",
        prompt=("The following is a casual conversation between two friends.\n\nFriend: " + event['inputTranscript'] + "\nAI: "),
        temperature=0.5,
        max_tokens=100,
        presence_penalty=0.6,
        stop=["Friend: ","AI: "]
    )
    content = query.choices[0].text
    
    # Printing the details for CloudWatch Logs
    print({
        "in": {
            "transcript": event['inputTranscript'],
            "confidence": event['transcriptions'][0]['transcriptionConfidence']
        },
        "out": {
            "message": content,
            "gptTokens": query.usage.total_tokens
        }
    })
    
    # Returning the object to be passed back to Lex
    return {
        "sessionState": {
            "dialogAction": {
                "type": "ElicitIntent"
            },
            "intent": {
                "name": "ChatGPT_Intent",
                "state": "Fulfilled"
            }
        },
        "messages": [
            {
                "contentType": "PlainText",
                "content": content
            }
        ]
    }