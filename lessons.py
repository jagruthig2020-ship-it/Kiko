"""Predefined localized Windows tasks; fully offline."""
from __future__ import annotations
import re

# Whitelisted Microsoft Settings URIs; no model-generated commands execute.
TASKS = {
 'bluetooth': dict(uri='ms-settings:bluetooth',
    words=['bluetooth','headphones','earbuds','pair device','బ్లూటూత్','హెడ్‌ఫోన్లు','బ్లూటూత్‌ను','ब्लूटूथ','हेडफ़ोन','हेडफोन'],
    en=['Bluetooth settings are open. Find the Bluetooth switch and turn it On.', 'To connect headphones, choose Add device, then Bluetooth. Select your headphones.', 'Look for Bluetooth under Settings → Bluetooth & devices. You click the switch yourself.'],
    te=['Bluetooth సెట్టింగ్స్ తెరిచాను. Bluetooth స్విచ్‌ను వెతికి On చేయండి.', 'హెడ్‌ఫోన్లు కనెక్ట్ చేయాలంటే Add device నొక్కి Bluetooth ఎంచుకోండి. తర్వాత మీ హెడ్‌ఫోన్లను ఎంచుకోండి.', 'Settings లో Bluetooth & devices తెరిచి Bluetooth స్విచ్‌ను చూడండి. మీరే నొక్కండి.'],
    hi=['Bluetooth सेटिंग्स खुल गई हैं। Bluetooth का स्विच ढूँढकर On करें।', 'हेडफ़ोन जोड़ने के लिए Add device, फिर Bluetooth चुनें और अपने हेडफ़ोन चुनें।', 'Settings में Bluetooth & devices खोलें और स्विच ढूँढें। उसे आप खुद दबाएँ।']),
 'wifi': dict(uri='ms-settings:network-wifi', words=['wi-fi','wifi','internet','network','వైఫై','వై-ఫై','ఇంటర్నెట్','वाईफाई','इंटरनेट'],
    en=['Wi-Fi settings are open. Turn Wi-Fi On.', 'Choose your network, select Connect, and enter its password yourself.', 'Open Network & internet → Wi-Fi, then find the On/Off switch.'],
    te=['Wi-Fi సెట్టింగ్స్ తెరిచాను. Wi-Fi స్విచ్‌ను On చేయండి.', 'మీ నెట్‌వర్క్‌ను ఎంచుకుని Connect నొక్కండి. పాస్‌వర్డ్ అడిగితే మీరే టైప్ చేయండి.', 'Network & internet లో Wi-Fi తెరిచి స్విచ్‌ను చూడండి.'],
    hi=['Wi-Fi सेटिंग्स खुल गई हैं। Wi-Fi स्विच On करें।', 'अपना नेटवर्क चुनें, Connect दबाएँ, और पासवर्ड खुद दर्ज करें।', 'Network & internet में Wi-Fi खोलकर स्विच देखें।']),
 'text': dict(uri='ms-settings:easeofaccess-display', words=['text size','font size','letters bigger','make text','bigger letters','అక్షరాలు','ఫాంట్','పెద్దగా','टेक्स्ट','अक्षर','फ़ॉन्ट'],
    en=['I opened accessibility display settings. Find Text size and move the slider right.', 'Select Apply. Check whether the letters are easier to read.', 'In Windows 11, go to Settings → Accessibility → Text size if this page differs.'],
    te=['అక్షరాల సెట్టింగ్స్ తెరిచాను. Text size స్లైడర్‌ను కుడివైపు జరపండి.', 'Apply నొక్కండి. అక్షరాలు స్పష్టంగా ఉన్నాయో చూసుకోండి.', 'ఈ పేజీలో Text size లేకపోతే Settings → Accessibility → Text size తెరవండి.'],
    hi=['टेक्स्ट की सेटिंग्स खुल गई हैं। Text size स्लाइडर दाईं ओर ले जाएँ।', 'Apply दबाएँ। देखें कि अक्षर पढ़ना आसान हुआ या नहीं।', 'अगर यहाँ Text size नहीं है, Settings → Accessibility → Text size खोलें।']),
 'display': dict(uri='ms-settings:display', words=['brightness','display','screen size','screen resolution','బ్రైట్‌నెస్','డిస్‌ప్లే','స్క్రీన్ వెలుగు','ब्राइटनेस','डिस्प्ले'],
    en=['Display settings are open. Look for Brightness or Scale.', 'Adjust the relevant slider a little and check the screen.', 'Under Settings → System → Display, find the Brightness or Scale control.'],
    te=['Display సెట్టింగ్స్ తెరిచాను. Brightness లేదా Scale ఎంచుకోండి.', 'కొంచెం మార్చి స్క్రీన్ ఎలా ఉందో చూడండి.', 'Settings → System → Display లో Brightness లేదా Scale ఉంటుంది.'],
    hi=['Display सेटिंग्स खुल गई हैं। Brightness या Scale ढूँढें।', 'थोड़ा बदलकर स्क्रीन देखें।', 'Settings → System → Display में Brightness या Scale मिलेगा।']),
 'sound': dict(uri='ms-settings:sound', words=['sound','volume','speaker','microphone settings','శబ్దం','వాల్యూమ్','స్పీకర్','आवाज़','वॉल्यूम','स्पीकर'],
    en=['Sound settings are open. Find the Volume slider.', 'Adjust Volume or choose a device under Output.', 'Under Settings → System → Sound, look for Output and Volume.'],
    te=['Sound సెట్టింగ్స్ తెరిచాను. Volume స్లైడర్‌ను చూడండి.', 'Volume మార్చండి లేదా Output లో స్పీకర్ ఎంచుకోండి.', 'Settings → System → Sound లో Output, Volume ఉంటాయి.'],
    hi=['Sound सेटिंग्स खुल गई हैं। Volume स्लाइडर ढूँढें।', 'Volume बदलें या Output में स्पीकर चुनें।', 'Settings → System → Sound में Output और Volume मिलेंगे।']),
 'mouse': dict(uri='ms-settings:mousetouchpad', words=['mouse settings','mouse speed','cursor speed','మౌస్','మౌస్ వేగం','माउस','कर्सर की गति'],
    en=['Mouse settings are open. Look for Mouse pointer speed.', 'Move the speed slider slightly, then try moving the mouse.', 'Find Mouse under Settings → Bluetooth & devices.'],
    te=['Mouse సెట్టింగ్స్ తెరిచాను. Mouse pointer speed చూడండి.', 'స్లైడర్ కొంచెం మార్చి మౌస్ కదిపి చూడండి.', 'Settings → Bluetooth & devices లో Mouse ఎంచుకోండి.'],
    hi=['Mouse सेटिंग्स खुल गई हैं। Mouse pointer speed ढूँढें।', 'स्लाइडर थोड़ा बदलकर माउस चलाएँ।', 'Settings → Bluetooth & devices में Mouse चुनें।']),
 'notifications': dict(uri='ms-settings:notifications', words=['notification','notifications','నోటిఫికేషన్','सूचनाएँ','नोटिफिकेशन'],
    en=['Notifications settings are open. Find the Notifications switch.', 'Choose which apps may send notifications.', 'Go to Settings → System → Notifications.'],
    te=['Notifications సెట్టింగ్స్ తెరిచాను. Notifications స్విచ్‌ను చూడండి.', 'ఏ యాప్‌లు నోటిఫికేషన్ పంపాలో ఎంచుకోండి.', 'Settings → System → Notifications తెరవండి.'],
    hi=['Notifications सेटिंग्स खुल गई हैं। Notifications स्विच ढूँढें।', 'चुनें कि कौन-से ऐप सूचना भेज सकते हैं।', 'Settings → System → Notifications खोलें।']),
}

def topic_for(text):
    t = text.casefold()
    matches = []
    for topic, cfg in TASKS.items():
        hits = [w for w in cfg['words'] if w.casefold() in t]
        if hits:
            matches.append((max(map(len, hits)), topic))
    return max(matches)[1] if matches else None

def human_message(lang, name):
    d = {
      'model': {'en':'The local AI model is not ready. Run: ollama pull gemma3:4b', 'te':'స్థానిక AI సిద్ధంగా లేదు. టెర్మినల్‌లో ollama pull gemma3:4b నడపండి.', 'hi':'स्थानीय AI तैयार नहीं है। टर्मिनल में ollama pull gemma3:4b चलाएँ।'},
      'consent':{'en':'For an unfamiliar app, turn on local screen permission first.', 'te':'కొత్త యాప్ కోసం ముందుగా స్థానిక స్క్రీన్ అనుమతిని ఆన్ చేయండి.', 'hi':'नए ऐप के लिए पहले स्थानीय स्क्रीन की अनुमति चालू करें।'},
      'switch':{'en':'Open the app you need help with during the countdown, then try again.', 'te':'కౌంట్‌డౌన్‌లో సహాయం కావలసిన యాప్ తెరిచి మళ్లీ ప్రయత్నించండి.', 'hi':'काउंटडाउन में वह ऐप खोलें जिसमें मदद चाहिए, फिर कोशिश करें।'},
      'done':{'en':'Saved as completed. Next time, try with fewer hints.', 'te':'పూర్తయిందని సేవ్ చేశాను. తర్వాత తక్కువ సూచనలతో ప్రయత్నించండి.', 'hi':'पूरा हुआ दर्ज किया। अगली बार कम संकेतों से कोशिश करें।'}
    }
    return d[name].get(lang,d[name]['en'])

