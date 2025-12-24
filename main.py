# Run "uv sync" to install the below packages
import random
import re
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
model_name="openai/gpt-oss-20b"

client = OpenAI(
    base_url="http://172.24.80.1:1234/v1",
    api_key="something-doesnt-matter",
)

def get_temperature(city:str) -> int:
    rastgele_tam_sayi = random.randint(-10, 35)
    return rastgele_tam_sayi

def main():
    print("Hello from agents!")
    user_input= input('Your Question: ')
    prompt=f"""
    You are a helpfull assitant and answer the questions in a friendly way
    You can also use tools if you feel like they help you provide
     a better and more correct answer depending on data that tool provides, but use get_temperature tools if user explicitly ask weather related info:

     - get_temperature(city:str) -> int: Get the current temperature for a given city
     
     If you want to use one of these tools, you should output the name of the tool and the arguments in the following format
        tool_name: arg1, arg2...     
     For example:
        get_temperature:Ankara

    With that in mind, answer the user's question:
    <user-question>
        {user_input}
    </user-question>
    if you request a tool, please output ONLY the tool call (as described above) and nothing else
    Do not include tags like <|start|>assistant<|channel|>commentary to=functions.get_temperature <|constrain|>json<|message|>"city":"Ankara" or JSON.
    Just return at this format:get_temperature:Ankara        
    """
    response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}]
        )
    reply=response.choices[0].message.content
    cleaned_reply= clean_model_reply(reply)
    print(cleaned_reply)

    if "get_temperature:" in cleaned_reply:
        # Metni parçalıyoruz: "get_temperature:Ankara" -> "Ankara"
        city = cleaned_reply.split(":")[1].strip()

       
        
        # Gerçek Python fonksiyonunu çağırıyoruz
        temperature = get_temperature(city)

        prompt=f"""
            You are a helpfull assitant and answer the questions in a friendly way
            Here is the users question :       
            <user-question>
                {user_input}
            </user-question> 

             You requested the tool call and result temperature is {temperature}
             
             Provide a logical answer to the user and offer what that temperature implies such as #take a sun glass# or #get thick clothes#
           
            Do not include tags like <|start|> <|channel|><|constrain|><|message|> or JSON.           
            """
        
        print(f"Sistem: Fonksiyon çalıştırıldı! Sonuç: {temperature}")
        
        # Şimdi sonucu modele tekrar verip düzgün cümle kurdurabilirsin
        final_response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "user", "content": prompt},
                #{"role": "assistant", "content": reply},
                #{"role": "system", "content": prompt}
            ]
        )
        print(f"Final Yanıtı: {final_response.choices[0].message.content}")
    else:
        print(f"Final Yanıtı: {reply}")


def clean_model_reply(raw_reply):
# Senaryo 1: Model zaten JSON içinde şehri veriyor
# Örn: ... "city":"Ankara" ...
    city_match = re.search(r'"city":\s*"(.*?)"', raw_reply)
    if city_match:
        city = city_match.group(1)
        return f"get_temperature:{city}"

    # Senaryo 2: Model sadece metin olarak Ankara dediyse (etiketler arasında)
    # Etiketleri ve JSON yapılarını temizle
    clean_text = re.sub(r'<\|.*?\|>', '', raw_reply) # <|etiketleri|> siler
    clean_text = re.sub(r'\{.*?\}', '', clean_text)  # {jsonları} siler

    return clean_text.strip()


if __name__ == "__main__":
    main()


