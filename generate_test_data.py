"""
Synthetic test data generator for the CSV Parsing Pipeline.
Generates realistic Google Forms-style survey CSVs.

Usage:
    python generate_test_data.py
Outputs:
    test_data_mentorship_event.csv
"""

import csv
import random
from datetime import datetime, timedelta




def random_timestamp(start_days_ago=7, end_days_ago=0):
    start = datetime.now() - timedelta(days=start_days_ago)
    end = datetime.now() - timedelta(days=end_days_ago)
    delta = end - start
    random_seconds = random.randint(0, int(delta.total_seconds()))
    dt = start + timedelta(seconds=random_seconds)
    return dt.strftime("%m/%d/%Y %H:%M:%S")  # Google Forms format


def pick(options, weights=None):
    return random.choices(options, weights=weights, k=1)[0]


# --- Response pools ---

OVERALL_RATINGS = [1, 2, 3, 4, 5]
OVERALL_WEIGHTS = [2, 5, 15, 45, 33]

BINGO_RATINGS = [1, 2, 3, 4, 5]
BINGO_WEIGHTS = [3, 7, 20, 40, 30]

HEAR_ABOUT = ["Instagram", "Discord", "A friend", "Email newsletter", "LinkedIn", "Club announcement"]
HEAR_WEIGHTS = [30, 25, 20, 12, 8, 5]

EXPECTATIONS_MET = ["Yes", "Partially", "No"]
EXPECT_WEIGHTS = [55, 30, 15]

ACCESSIBILITY_DIFFICULTY = ["Yes", "No"]
ACCESSIBILITY_WEIGHTS = [12, 88]

LIKES_DISLIKES = [
    "I really enjoyed the networking aspect and meeting people from different programs.",
    "The Human Bingo was a great icebreaker. Wish it lasted longer.",
    "Liked the energy in the room. Disliked that it felt a bit rushed at the end.",
    "Loved seeing so many mentors in one place. The food was also great!",
    "The event was well organised. I disliked that parking was difficult to find.",
    "Great atmosphere. I felt a bit lost at the start — a clearer agenda would help.",
    "I liked meeting new people. The bingo activity was fun but confusing at first.",
    "Really enjoyed the casual format. Would have liked more structured mentor intros.",
    "Everything was good! The only thing was the room got very loud.",
    "The icebreakers were fun. I didn't dislike anything honestly.",
    "Really positive experience overall. Mentors were approachable and friendly.",
    "Liked the diversity of mentors available. Didn't like that some sessions overlapped.",
    "The event had a great vibe! I wish there were more seats available.",
    "Fun event overall. It would've been better with name tags for everyone.",
    "I liked how welcoming the organisers were. Everything ran smoothly.",
    "Great initiative. I disliked that the event was shorter than expected.",
]

EXPECTATIONS_TEXT = [
    "I expected to meet a mentor and learn about the program. It met my expectations fully.",
    "I came hoping to network and get program details — both happened, so yes.",
    "I expected it to be more informational. It was more social, which was still good.",
    "My expectations were mostly met. Would've liked a bit more structured Q&A.",
    "Totally met expectations. I got matched with a great mentor.",
    "I expected more one-on-one time with mentors. It was more of a group setting.",
    "It exceeded expectations honestly. Very welcoming environment.",
    "I wasn't sure what to expect but came away impressed.",
    "Partially met. I was hoping for clearer information on how the matching works.",
    "Yes, met expectations. The mentors were engaging and the vibe was great.",
    "Mostly yes. A printed schedule would have helped navigate the event.",
    "It met my expectations. I learned a lot about the program and connected with people.",
]

SEEN_MORE_OF = [
    "More one-on-one time with mentors.",
    "More diverse mentors from different industries.",
    "I wish there were more structured activities beyond bingo.",
    "More clarity on how the mentorship matching process works.",
    "More interactive sessions, maybe a panel Q&A.",
    "I would've loved more info on what being a mentee involves week-to-week.",
    "Longer event time — it felt a bit short.",
    "More food options would've been nice.",
    "More mentors from the tech sector specifically.",
    "",  # optional — some leave it blank
    "",
    "",
]

ACCESSIBILITY_ISSUES = [
    "The venue had no ramp near the main entrance.",
    "The room was too loud for those with hearing sensitivity.",
    "I use a wheelchair and the registration desk was too high.",
    "No ASL interpreter was available.",
    "Lighting was quite harsh — could be an issue for some.",
]

ADDITIONAL_COMMENTS = [
    "Overall a great event. Keep it up!",
    "Would love to see this happen more than once a year.",
    "The organisers did a fantastic job. Very welcoming.",
    "Please send out the mentor bios in advance next time.",
    "Nothing to add — it was great.",
    "Consider adding a feedback form at the event itself.",
    "More advertising on campus would help bring in more attendees.",
    "Loved it. Already looking forward to the next one.",
    "A follow-up email with mentor contact info would be helpful.",
    "Great event. The bingo was a highlight.",
    "",
    "",
    "",
]

# --- Generator ---

HEADERS = [
    "Timestamp",
    "How would you rate this event overall?",
    "How would you rate the Human Bingo activity?",
    "What did you like or dislike about it?",
    "How did you hear about the mentorship program?",
    "What did you expect from the event and did it meet your expectations?",
    "For the following, were your expectations met? [Learned about program]",
    "For the following areas, were your expectations met? [Met new people]",
    "[Optional] We'd love to hear your thoughts on the above. What do you wish you could've seen more of?",
    "Did you experience any difficulty accessing or participating in the event?",
    "How did we not meet your accessibility accommodations?",
    "Do you have additional comments or feedback for us on how we improve?",
]


def generate_row():
    had_accessibility_issue = pick(ACCESSIBILITY_DIFFICULTY, ACCESSIBILITY_WEIGHTS) == "Yes"

    return [
        random_timestamp(),
        pick(OVERALL_RATINGS, OVERALL_WEIGHTS),
        pick(BINGO_RATINGS, BINGO_WEIGHTS),
        pick(LIKES_DISLIKES),
        pick(HEAR_ABOUT, HEAR_WEIGHTS),
        pick(EXPECTATIONS_TEXT),
        pick(EXPECTATIONS_MET, EXPECT_WEIGHTS),
        pick(EXPECTATIONS_MET, EXPECT_WEIGHTS),
        pick(SEEN_MORE_OF),
        "Yes" if had_accessibility_issue else "No",
        pick(ACCESSIBILITY_ISSUES) if had_accessibility_issue else "",
        pick(ADDITIONAL_COMMENTS),
    ]


def generate_csv(filename="test_data_mentorship_event.csv", rows=60):
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(HEADERS)
        for _ in range(rows):
            writer.writerow(generate_row())
    print(f"Generated {rows} rows -> {filename}")


if __name__ == "__main__":
    generate_csv()
