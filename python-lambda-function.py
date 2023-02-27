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


def get_session_attributes(intent_request):
    sessionState = intent_request['sessionState']
    if 'sessionAttributes' in sessionState:
        return sessionState['sessionAttributes']

    return {}


def get_slots(intent_request):
    return intent_request['sessionState']['intent']['slots']


def get_slot(intent_request, slotName):
    slots = get_slots(intent_request)
    if slots is not None and slotName in slots and slots[slotName] is not None:
        return slots[slotName]['value']['interpretedValue']
    else:
        return None


def close(intent_request, session_attributes, fulfillment_state, message):
    intent_request['sessionState']['intent']['state'] = fulfillment_state
    return {
        'sessionState': {
            'sessionAttributes': session_attributes,
            'dialogAction': {
                'type': 'Close'
            },
            'intent': intent_request['sessionState']['intent']
        },
        'messages': [message],
        'sessionId': intent_request['sessionId'],
        'requestAttributes': intent_request['requestAttributes'] if 'requestAttributes' in intent_request else None
    }


def elicit_intent(intent_request, session_attributes, message):
    return {
        'sessionState': {
            'dialogAction': {
                'type': 'ElicitIntent'
            },
            'sessionAttributes': session_attributes
        },
        'messages': [message] if message != None else None,
        'requestAttributes': intent_request['requestAttributes'] if 'requestAttributes' in intent_request else None
    }


def createDrunkResultText(session_attributes):
    if "small" in session_attributes and "medium" in session_attributes and "large":
        flag = False
        text = "You drunk "
        if int(session_attributes['small']) >= 1:
            text = text + str(session_attributes['small']) + " small glasses"
            flag = True
        if int(session_attributes['medium']) >= 1:
            if flag:
                text = text + " and"
            text = text + " " + str(session_attributes['medium']) + " medium glasses"
            flag = True
        if int(session_attributes['large']) >= 1:
            if flag:
                text = text + " and"
            text = text + " " + str(session_attributes['large']) + " large glasses"
        text = text + " of water today."
        return text
    else:
        return "You have no stats for today."


def lambda_handler(event, context):
    intent_name = event['sessionState']['intent']['name']
    if intent_name == 'DrankLiquidIntent':
        session_attributes = get_session_attributes(event)
        numberOfGlass = get_slot(event, 'numberOfGlass')
        sizeOfBeverage = get_slot(event, 'sizeOfBeverage')

        print("session_attributes_before")
        print(session_attributes)

        if "small" in session_attributes and "medium" in session_attributes and "large":
            # add some water to previous result
            print("add some water to previous result")
            session_attributes[sizeOfBeverage] = int(session_attributes[sizeOfBeverage]) + int(numberOfGlass)
        else:
            # add some water first time
            print("add some water first time")
            updated_session_attributes = {
                "small": 0,
                "medium": 0,
                "large": 0
            }
            updated_session_attributes[sizeOfBeverage] = numberOfGlass
            session_attributes = updated_session_attributes

        print("session_attributes_afer")
        print(session_attributes)

        message = {
            'contentType': 'PlainText',
            'content': createDrunkResultText(session_attributes)
        }
        fulfillment_state = "Fulfilled"

        return close(event, session_attributes, fulfillment_state, message)
    elif intent_name == 'ReadDailyOverviewIntent':
        session_attributes = get_session_attributes(event)

        drunk_result_text = createDrunkResultText(session_attributes)
        if drunk_result_text != "You have no stats for today.":
            text = "Ok. This is your stats for today. " + createDrunkResultText(session_attributes)
        else:
            text = drunk_result_text
        message = {
            'contentType': 'PlainText',
            'content': text
        }
        fulfillment_state = "Fulfilled"

        return close(event, session_attributes, fulfillment_state, message)
    elif intent_name == 'ResetDailyOverviewIntent':
        session_attributes = {}
        message = {
            'contentType': 'PlainText',
            'content': 'Your daily stats have been successfully deleted.'
        }
        fulfillment_state = "Fulfilled"

        return close(event, session_attributes, fulfillment_state, message)
    else:
        # Passing the message to OpenAI
        query = openai.Completion.create(
            model="text-davinci-003",
            prompt=("The following is a casual conversation between two friends.\n\nFriend: " + event[
                'inputTranscript'] + "\nAI: "),
            temperature=0.5,
            max_tokens=100,
            presence_penalty=0.6,
            stop=["Friend: ", "AI: "]
        )
        content = query.choices[0].text

        # Printing the details for CloudWatch Logs
        print({
            "in": {
                "transcript": event['inputTranscript'],
                "confidence": event['transcriptions'][0]['transcriptionConfidence']
            },
            "out": {
                "message": "AI" + content,
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
                    "name": "FallbackIntent",
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
