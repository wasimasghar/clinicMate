# generate_reviews.py
# Creates realistic doctor reviews (English, Urdu, Roman Urdu) and saves them to data/reviews.json.

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
RANDOM_SEED = 42  # same seed = same names, ratings and comments on every run

REVIEWER_NAMES = [
    "Ahmed K.", "Sana M.", "Usman A.", "Ayesha R.", "Bilal S.", "Hira T.", "Zain U.",
    "Maham F.", "Imran Q.", "Rabia N.", "Hassan J.", "Iqra B.", "Faizan H.", "Mehak S.",
    "Tariq M.", "Noor E.", "Kashif R.", "Amna L.", "Shoaib Z.", "Laiba K.", "Naveed I.",
    "Sidra P.", "Owais G.", "Komal Y.", "Verified Patient", "Verified Patient",
]

POSITIVE_COMMENTS = [
    "Very professional doctor. Listened to all my problems patiently.",
    "Doctor sahab ne bohat achi tarah check kiya aur sab kuch samjhaya.",
    "ڈاکٹر صاحب بہت اچھے ہیں، تسلی سے بات سنی اور صحیح علاج کیا۔",
    "Excellent experience. Clinic was clean and staff was helpful.",
    "Bohat acha doctor hai, dawai se 3 din mein farq par gaya.",
    "Highly recommended. Explained everything in simple words.",
    "Time par check kiya, zyada wait nahi karna para.",
    "میں بہت مطمئن ہوں، ڈاکٹر نے غیر ضروری ٹیسٹ نہیں لکھے۔",
    "Very kind with elderly patients. My father was very comfortable.",
    "Fee reasonable hai aur treatment bhi acha hai.",
    "Best doctor I have visited in years. Will come again.",
    "Doctor ne follow-up par bhi achi tarah guide kiya.",
]

NEUTRAL_COMMENTS = [
    "Doctor is good but waiting time was more than one hour.",
    "Theek tha, lekin checkup bohat jaldi khatam kar diya.",
    "ڈاکٹر ٹھیک ہیں لیکن کلینک میں رش بہت تھا۔",
    "Treatment okay, but fee is a bit high.",
    "Average experience. Parking was a problem.",
    "Doctor acha hai magar staff ka rawaiya theek nahi tha.",
]

NEGATIVE_COMMENTS = [
    "Waited two hours and doctor gave only five minutes.",
    "Bohat zyada tests likh diye, faida nahi hua.",
    "ڈاکٹر نے بات پوری نہیں سنی، مایوسی ہوئی۔",
    "Appointment time par nahi mila, bohat late check kiya.",
    "Not satisfied. Problem is still the same after two visits.",
    "Staff rude tha aur clinic mein safai nahi thi.",
]

# Extra positive comments that match the doctor's specialty
SPECIALTY_COMMENTS = {
    "Dermatologist": ["My acne cleared up in two months.", "Skin allergy bilkul theek ho gayi."],
    "Gynecologist": ["Very caring during my pregnancy.", "PCOS ke bare mein bohat acha samjhaya."],
    "Pediatrician": ["Very gentle with my baby.", "Bachay ka bukhar 2 din mein utar gaya."],
    "Cardiologist": ["Explained my ECG report clearly.", "BP ab control mein hai, shukriya doctor sahab."],
    "Dentist": ["Root canal was painless.", "Daant ka dard foran khatam ho gaya."],
    "ENT Specialist": ["Sinus problem finally under control.", "Kaan ka infection theek ho gaya."],
    "Audiologist": ["Hearing aid fitting was perfect, my mother can hear clearly now.", "Hearing test bohat detail se kiya."],
    "Oncologist": ["Very supportive during my mother's chemotherapy.", "Cancer treatment ka poora plan tasalli se samjhaya."],
    "Endocrinologist": ["My sugar is finally under control.", "Thyroid ki dawai sahi adjust ki."],
    "Pulmonologist": ["Asthma attacks reduced a lot.", "Smog season mein saans ka masla theek hua."],
    "Gastroenterologist": ["Acidity problem solved.", "Hepatitis C ka ilaaj kamyab raha."],
    "Allergist": ["Finally found the cause of my sneezing.", "Perfume aur dhool wali allergy ab control mein hai."],
    "Neurologist": ["Migraine attacks are much less now.", "Chakkar aana band ho gaye."],
    "Orthopedic Surgeon": ["Knee pain much better after treatment.", "Kamar dard mein bohat aram aaya."],
    "Psychiatrist": ["Felt heard and not judged.", "Anxiety mein bohat behtari aayi."],
}


def pick_rating(doctor_quality: float) -> int:
    """Rating near the doctor's quality, sometimes higher or lower, kept between 1 and 5."""
    rating = round(random.gauss(doctor_quality, 0.8))
    return max(1, min(5, rating))


def pick_comment(rating: int, specialty: str) -> str:
    """Comment that matches the rating (good, average or bad)."""
    if rating >= 4:
        options = POSITIVE_COMMENTS + SPECIALTY_COMMENTS.get(specialty, [])
    elif rating == 3:
        options = NEUTRAL_COMMENTS
    else:
        options = NEGATIVE_COMMENTS
    return random.choice(options)


def random_date_last_year() -> str:
    """A random date and time within the last 365 days."""
    days_ago = random.randint(1, 365)
    hours_ago = random.randint(0, 23)
    created = datetime.now(timezone.utc) - timedelta(days=days_ago, hours=hours_ago)
    return created.isoformat(timespec="seconds")


def generate_reviews() -> list[dict]:
    random.seed(RANDOM_SEED)
    doctors = json.loads((DATA_DIR / "doctors.json").read_text(encoding="utf-8"))

    reviews = []
    for doctor in doctors:
        doctor_quality = random.uniform(3.6, 4.8)  # some doctors are better than others
        for _ in range(random.randint(4, 7)):
            rating = pick_rating(doctor_quality)
            reviews.append({
                "doctor": doctor["full_name"],
                "reviewer_name": random.choice(REVIEWER_NAMES),
                "rating": rating,
                "comment": pick_comment(rating, doctor["specialty"]),
                "created_at": random_date_last_year(),
            })
    return reviews


def save_reviews(reviews: list[dict]) -> None:
    output_file = DATA_DIR / "reviews.json"
    output_file.write_text(json.dumps(reviews, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {len(reviews)} reviews to {output_file}")


if __name__ == "__main__":
    save_reviews(generate_reviews())