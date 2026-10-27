
from flask import Flask, render_template, request, jsonify
from difflib import get_close_matches
from collections import defaultdict
import csv
import os
import re

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DICTIONARY_FILE = os.path.join(BASE_DIR, "rumi-jawi.tsv")

# Kamus contoh untuk ujian awal.
# Semak ejaan ini dengan rujukan Jawi yang sahih.
jawi_dictionary = {
    "saya": "ساي",
    "awak": "اوق",
    "makan": "ماکن",
    "minum": "مينوم",
    "buku": "بوکو",
    "rumah": "رومه",
    "sekolah": "سکوله",
    "bahasa": "بهاس",
    "melayu": "ملايو",
    "jawi": "جاوي",
    "suka": "سوک",
    "dan": "دان",
    "ini": "ايني",
    "itu": "ايتو",
    "air": "اءير",
    "ayam": "ايم",
    "bola": "بولا",
    "membaca": "ممباچ",
}

reverse_dictionary = defaultdict(list)

def rebuild_reverse_dictionary():
    reverse_dictionary.clear()
    for rumi, jawi in jawi_dictionary.items():
        if rumi not in reverse_dictionary[jawi]:
            reverse_dictionary[jawi].append(rumi)


def load_dictionary():
    if not os.path.isfile(DICTIONARY_FILE):
        print("Fail kamus tiada. Menggunakan kamus contoh.")
        return

    try:
        with open(
            DICTIONARY_FILE,
            "r",
            encoding="utf-8-sig",
            newline=""
        ) as file:
            rows = list(csv.reader(file, delimiter="\t"))

        if not rows:
            print("Fail kamus kosong.")
            return

        header = [cell.strip().lower() for cell in rows[0]]

        if "rumi" in header and "jawi" in header:
            rumi_index = header.index("rumi")
            jawi_index = header.index("jawi")
            data_rows = rows[1:]
        else:
            rumi_index, jawi_index = 0, 1
            data_rows = rows

        for row in data_rows:
            if len(row) <= max(rumi_index, jawi_index):
                continue

            rumi = row[rumi_index].strip().lower()
            jawi = row[jawi_index].strip()

            if rumi and jawi:
                jawi_dictionary[rumi] = jawi

        print(f"Jumlah perkataan: {len(jawi_dictionary)}")

    except (OSError, csv.Error) as error:
        print(f"Ralat membaca kamus: {error}")


load_dictionary()
rebuild_reverse_dictionary()

WORD_PATTERN = r"[^\W\d_]+(?:[-'’][^\W\d_]+)*"


def convert_to_jawi(text):
    def replace_word(match):
        word = match.group(0)
        return jawi_dictionary.get(word.lower(), word)

    return re.sub(WORD_PATTERN, replace_word, text)


def convert_to_rumi(text):
    # Padankan perkataan Jawi dan kekalkan tanda baca.
    tokens = re.findall(r"[\u0600-\u06FF]+|[^\u0600-\u06FF]+", text)
    result = []

    for token in tokens:
        if re.fullmatch(r"[\u0600-\u06FF]+", token):
            matches = reverse_dictionary.get(token, [])
            if len(matches) == 1:
                result.append(matches[0])
            elif len(matches) > 1:
                # Pilihan pertama sahaja; perkataan ini mungkin
                # mempunyai lebih daripada satu bacaan Rumi.
                result.append(matches[0])
            else:
                result.append(token)
        else:
            result.append(token)

    return "".join(result)


def check_spelling(text):
    results = []
    known_words = set(jawi_dictionary.keys())

    for match in re.finditer(WORD_PATTERN, text):
        word = match.group(0)
        lower_word = word.lower()

        if lower_word in known_words:
            continue

        # Jangan beri cadangan untuk perkataan yang terlalu pendek.
        if len(lower_word) < 3:
            continue

        suggestions = get_close_matches(
            lower_word,
            list(known_words),
            n=3,
            cutoff=0.78
        )

        if suggestions:
            results.append({
                "word": word,
                "suggestions": suggestions
            })

    return results


def read_text():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")

    if not isinstance(text, str):
        return None, (
            jsonify({"error": "Input mestilah teks."}), 400
        )

    if not text.strip():
        return None, (
            jsonify({"error": "Sila masukkan teks dahulu."}), 400
        )

    if len(text) > 10000:
        return None, (
            jsonify({"error": "Teks melebihi had 10000 aksara."}), 400
        )

    return text, None


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/convert", methods=["POST"])
def convert():
    text, error = read_text()
    if error:
        return error

    return jsonify({"result": convert_to_jawi(text)})


@app.route("/reverse", methods=["POST"])
def reverse():
    text, error = read_text()
    if error:
        return error

    return jsonify({"result": convert_to_rumi(text)})


@app.route("/spellcheck", methods=["POST"])
def spellcheck():
    text, error = read_text()
    if error:
        return error

    return jsonify({
        "suggestions": check_spelling(text)
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )
