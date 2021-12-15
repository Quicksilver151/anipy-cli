from bs4 import BeautifulSoup
import requests
import re
import subprocess as sp



GREEN = '\033[92m'
ERROR = '\033[93m'
END = '\x1b[0m'

headers = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.69 Safari/537.36 Edg/95.0.1020.44"
    }

def get_embed_url(url):
    
    r = requests.get(url)
    soup = BeautifulSoup(r.content, "html.parser")
    link = soup.find("a", {"href": "#", "rel": "100"})
    return f'https:{link["data-video"]}'

def get_video_url(embed_url):

    r = requests.get(embed_url, headers=headers)
    link = re.search(r"\s*sources.*", r.text).group()
    link = re.search(r"https:.*(m3u8)|(mp4)", link).group()
    
    return link

def quality(video_url, embed_url, quality="best"):

    # Using cUrl here because I just couldnt find a soulution 
    # for getting the quality-subprofiles of the video. 
    # Somehow cUrl just works so im using it here.
    cURL = 'curl -s --referer {0} {1}'.format(embed_url, video_url)
    
    response = sp.check_output(cURL)
    qualitys = re.findall(r'\d+p', response.decode('utf-8')) 
     
    for i in range(len(qualitys)):
        qualitys[i] = qualitys[i].replace("p", "")
    
    if quality == "best" or quality == "worst":
        if quality == "best":
            quality = qualitys[-1]
        else:
            quality = qualitys[0]
    else:
        if quality in qualitys:
            quality = quality
        else:
            quality = qualitys[-1]
            print(ERROR + "Your quality is not avalible using: " + qualitys[-1] + END)
            pass
    
    try:
        quality = quality.replace("p", "")
    except:
        pass
    
    url = video_url.replace("m3u8", "") + quality + ".m3u8"
    
    
    return url

    
    