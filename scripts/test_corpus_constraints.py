"""Tests for corpus_constraints.py, built from real corpus v0 failures (issue #44 and the quiz-sample
review). Run with: uv run pytest scripts/test_corpus_constraints.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from corpus_constraints import (
    has_verse_marker, honorifics_preserved, is_quiz, is_short, normalize_candidate, normalize_ending,
    option_labels, options_preserved, readability_units, source_ending, strip_tashkeel, structure_gates,
    verses_preserved, word_count,
)


def test_strip_tashkeel_keeps_letters():
    assert strip_tashkeel("أُكْمِلُ الدَّرْسَ") == "أكمل الدرس"
    assert strip_tashkeel("ســـــلامٌ") == "سلام"
    assert strip_tashkeel("مرحبا بالعالم") == "مرحبا بالعالم"


def test_word_count_and_short():
    assert word_count("حياةٌ مثيرة") == 2
    assert is_short("ســـــلامٌ علــــى كــــل إنــســـــان")
    assert not is_short("أما أقدم القطع الزجاجية المعروفة، فترجع إلى منتصف الألفية الثالثة")


def test_quiz_ignores_ikhtar_inside_other_words():
    assert not is_quiz("أول براءة اختراع لقلم حبر جاف سجلت في 30 أكتوبر 1888")
    assert not is_quiz("كل همه أن يمنع القنابل من اختراق مجال الأرض،")
    assert not is_quiz("قصدت أحد المساجد، واخترت بعد صلاة العشاء ركنًا بعيدًا")
    assert is_quiz("اختر الإجابة الصحيحة: (أ) نعم (ب) لا")
    assert is_quiz("نبات ذو فلقة واحدة (أ) الحمص (ب) العدس (ج) الذرة (د) الفول")


def test_option_labels_both_forms():
    assert option_labels("(أ) الحمص (ب) العدس (ج) الذرة") == ["أ", "ب", "ج"]
    assert option_labels("ما حكمها؟ أ) إخفاء. ب) إظهار. ج) إقلاب") == ["أ", "ب", "ج"]
    assert option_labels("ذهب أحمد إلى السوق") == []


def test_options_collapsed_into_prose_fails():
    # ID 20201360010: a single-answer MCQ turned into a claim that all three options are true.
    src = "يتكون الجليد بسرعة أكبر على الطرق: (أ) التي يقع عليها ظل (ب) المسطحة (ج) التي سطحها متعرج وفيه تجاويف"
    bad = "يتكون الجليد أسرع على ثلاث طرق: طريق عليه ظل، وطريق مستوٍ، وطريق سطحه غير مستوٍ وفيه حفر."
    good = "يتكون الجليد أسرع على الطرق: (أ) التي عليها ظل (ب) المستوية (ج) التي سطحها غير مستو وفيه حفر"
    assert not options_preserved(src, bad)
    assert options_preserved(src, good)


def test_options_dropped_or_reordered_fails():
    src = "(أ) صح (ب) خطأ"
    assert not options_preserved("الأبتر هو مقطوع النسل " + src, "الأبتر هو الذي لا أولاد له.")
    assert not options_preserved("س؟ (أ) x (ب) y (ج) z", "س؟ (أ) x (ج) z (ب) y")
    assert options_preserved("جملة عادية بلا خيارات", "جملة بسيطة")


def test_honorifics():
    src = "من هو مؤذن الرسول صلى الله عليه وسلم؟"
    assert not honorifics_preserved(src, "من كان يؤذن للرسول؟")
    assert honorifics_preserved(src, "من كان يؤذن للرسول صلى الله عليه وسلم؟")
    assert honorifics_preserved(src, "من كان يؤذن للرسول ﷺ؟")
    src2 = "(أ) أبو بكر الصديق رضي الله عنه (ب) عمر بن الخطاب رضي الله عنه"
    assert not honorifics_preserved(src2, "(أ) أبو بكر (ب) عمر")
    # عنه must not be satisfied by عنهم, nor عنهم counted as عنه
    assert not honorifics_preserved("علي رضي الله عنه", "الصحابة رضي الله عنهم")
    assert honorifics_preserved("علي رضي الله عنه", "علي رضي الله عنه. وهو صحابي.")


def test_verses():
    src = "قال الله تعالى: ﴿وَلْتَكُنْ مِنْكُمْ أُمَّةٌ يَدْعُونَ إِلَى الْخَيْرِ﴾ صدق الله"
    assert has_verse_marker(src)
    assert not verses_preserved(src, "قال الله: ليكن منكم جماعة يدعون إلى الخير.")
    assert verses_preserved(src, "قال الله: ﴿ولتكن منكم أمة يدعون إلى الخير﴾ وهذا أمر.")
    assert has_verse_marker("قوله تعالى [ الذي علم بالقلم ]")
    assert not has_verse_marker("قال المعلم إن الدرس مهم")


def test_source_ending():
    assert source_ending("فترجع إلى منتصف الألفية الثالثة قبل الميلاد،") == "،"
    assert source_ending("قال الله تعالى، جل جلال الله:") == ":"
    assert source_ending("ولو نطق الزمان لنا هجانا") == "none"
    assert source_ending("ذهب الولد إلى المدرسة.") == "stop"
    assert source_ending("المدينة التي تعيش على الزراعة هي ………") == "ellipsis"
    assert source_ending('قال: "اذهب إلى البيت."') == "stop"


def test_normalize_ending():
    assert normalize_ending("قبل الميلاد،", "ترجع إلى ما قبل الميلاد.") == "ترجع إلى ما قبل الميلاد،"
    assert normalize_ending("قال الله تعالى، جل جلال الله:", "قال الله، وهو عظيم.") == "قال الله، وهو عظيم:"
    assert normalize_ending("ولو نطق الزمان لنا هجانا", "لو صار للزمن صوت، للامنا.") == "لو صار للزمن صوت، للامنا"
    assert normalize_ending("ذهب الولد.", "ذهب الطفل.") == "ذهب الطفل."
    assert normalize_ending("السميع هو ………", "السميع هو ………") == "السميع هو ………"
    assert normalize_ending("قال لي،", 'قال: "تعال."') == 'قال: "تعال،"'
    # no mark on the candidate but the source continues: append the source's mark
    assert normalize_ending("من المدن الكبيرة:", "من المدن الكبيرة") == "من المدن الكبيرة:"


def test_normalize_candidate_strips_and_keeps_option_lines():
    src = "السميع هو ………… (أ) الله يعلم (ب) الله يسمع"
    cand = "السَّمِيعُ هو …………\n(أ)  الله  يعرف\n(ب) الله يسمع"
    out = normalize_candidate(src, cand)
    assert out == "السميع هو …………\n(أ) الله يعرف\n(ب) الله يسمع"
    assert structure_gates(src, out) == {"options_preserved": True, "honorifics_preserved": True, "verses_preserved": True}


def test_readability_units():
    assert readability_units("جملة أولى. جملة ثانية؟ ثالثة") == ["جملة أولى.", "جملة ثانية؟", "ثالثة"]
    assert readability_units("ما عاصمة مصر؟ (أ) القاهرة (ب) الجيزة") == ["ما عاصمة مصر؟"]
    assert readability_units("سطر\n(أ) واحد\n(ب) اثنان") == ["سطر"]
    assert readability_units("لا خيارات هنا (أ) فقط") == ["لا خيارات هنا (أ) فقط"]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("all passed")
