"""Writes the 19 hand-made cases (data/cases.json). They work offline and are checked by the Referee.
Run it only to reset the demo library: it overwrites data/cases.json."""
import json
from storage import CASES_FILE

# (title, category, tamper, article, original_sentence, original_value, false_value, clues, explanation)
# In the clues, the FALSE one starts with "!".
RAW = [
("Marie Curie", "famous people", "date",
 "Marie Curie was born in Warsaw in 1867. She moved to Paris to study physics and mathematics. In 1898 she and her husband Pierre announced the discovery of two new elements, polonium and radium. She won the Nobel Prize in Physics in 1903, together with Pierre Curie and Henri Becquerel. She won the Nobel Prize in Chemistry in 1911 and became the first person to win Nobel Prizes in two different sciences. She died in 1934 from an illness linked to radiation.",
 "She won the Nobel Prize in Chemistry in 1911 and became the first person to win Nobel Prizes in two different sciences.", "1911", "1921",
 ["The subject was born in Warsaw in 1867.", "In 1898 the subject and a spouse announced two new elements, polonium and radium.",
  "The subject shared a Nobel Prize in Physics in 1903.", "!The subject won a Nobel Prize in Chemistry in 1921.", "The subject died in 1934 from an illness linked to radiation."],
 "The Nobel Prize in Chemistry was won in 1911, not 1921."),
("Eiffel Tower", "France", "place",
 "The Eiffel Tower is an iron lattice tower on the Champ de Mars in Paris, France. It was designed by the engineering company of Gustave Eiffel. Construction began in 1887 and the structure was finished in 1889 for the World's Fair. At that time it was the tallest man-made structure in the world. Today the tower is about 330 metres tall. Millions of visitors climb or ride up it every year.",
 "The Eiffel Tower is an iron lattice tower on the Champ de Mars in Paris, France.", "Paris", "Lyon",
 ["Construction of this iron structure began in 1887.", "!This iron lattice structure stands on the Champ de Mars in Lyon, France.",
  "It was finished in 1889 for a World's Fair.", "It is about 330 metres tall today.", "When it was finished, it was the tallest man-made structure in the world."],
 "The Champ de Mars is in Paris, not in Lyon."),
("Hangul", "Korea", "number",
 "Hangul is the writing system of the Korean language. It was created in 1443 by King Sejong the Great and his scholars. It was officially announced in 1446 in a document called Hunminjeongeum. Modern Hangul has 24 basic letters. The letters are grouped into blocks that represent syllables. South Korea celebrates Hangul Day every year in October.",
 "Modern Hangul has 24 basic letters.", "24", "28",
 ["It was created in 1443 by a king named Sejong and his scholars.", "It was officially announced in 1446.", "Its letters are grouped into blocks that represent syllables.",
  "A country celebrates a special day for it every year in October.", "!The modern version of this alphabet has 28 basic letters."],
 "Modern Hangul has 24 basic letters, not 28."),
("Apollo 11", "science", "person",
 "Apollo 11 was the American space mission that first landed humans on the Moon. It was launched on 16 July 1969. Neil Armstrong and Buzz Aldrin landed on the Moon on 20 July 1969. Michael Collins remained in lunar orbit in the command module. Armstrong was the first person to step onto the surface. The crew returned safely to Earth on 24 July 1969.",
 "Michael Collins remained in lunar orbit in the command module.", "Michael Collins", "Frank Borman",
 ["It was launched in July 1969.", "Two astronauts landed on the surface on 20 July 1969.", "!An astronaut named Frank Borman stayed in orbit around the Moon in the command module.",
  "Neil Armstrong was the first person to step onto the surface.", "The crew returned safely to Earth on 24 July 1969."],
 "Michael Collins stayed in orbit, not Frank Borman."),
("Berlin Wall", "history", "number",
 "The Berlin Wall was a guarded barrier that surrounded West Berlin and separated it from East Germany. Construction began on 13 August 1961. It was about 155 kilometres long. It fell on 9 November 1989. Germany was reunified in 1990.",
 "It was about 155 kilometres long.", "155", "255",
 ["Construction began in 1961.", "It surrounded a city and separated it from East Germany.", "!The barrier was about 255 kilometres long.", "It fell on 9 November 1989.", "Germany was reunified in 1990."],
 "The barrier was about 155 kilometres long, not 255."),
("Titanic", "history", "place",
 "Titanic was a British passenger ship. It sank in the North Atlantic Ocean on 15 April 1912 after hitting an iceberg. The ship left Southampton on its first voyage to New York City. About 2,224 people were on board. More than 1,500 of them died. It was built in Belfast by the company Harland and Wolff.",
 "It was built in Belfast by the company Harland and Wolff.", "Belfast", "Liverpool",
 ["It sank in the North Atlantic Ocean in 1912 after hitting an iceberg.", "The ship left Southampton on its first voyage.", "About 2,224 people were on board.",
  "More than 1,500 people died.", "!It was built in Liverpool by the company Harland and Wolff."],
 "The ship was built in Belfast, not in Liverpool."),
("Leonardo da Vinci", "famous people", "date",
 "Leonardo da Vinci was an Italian artist and inventor. He was born in 1452 in the town of Vinci, near Florence. He painted the Mona Lisa and The Last Supper. He worked for many years in Milan. He died in 1519 in France.",
 "He was born in 1452 in the town of Vinci, near Florence.", "1452", "1472",
 ["He was an Italian artist and inventor.", "!The artist was born in 1472 near Florence.", "He painted the Mona Lisa and The Last Supper.", "He worked for many years in Milan.", "He died in 1519 in France."],
 "He was born in 1452, not in 1472."),
("Isaac Newton", "famous people", "place",
 "Isaac Newton was an English mathematician and physicist. He studied at Trinity College in Cambridge. In 1687 he published a book called Principia, which describes the laws of motion and gravity. He also built an early type of reflecting telescope. He died in 1727 in London.",
 "He died in 1727 in London.", "London", "Edinburgh",
 ["He was an English mathematician and physicist.", "He studied at Trinity College in Cambridge.", "He published a book about the laws of motion and gravity in 1687.", "He built an early type of reflecting telescope.", "!He died in 1727 in Edinburgh."],
 "He died in London, not in Edinburgh."),
("Python (programming language)", "computing and electronics basics", "person",
 "Python is a programming language created by Guido van Rossum. Its first version was released in 1991. The language is known for its simple and readable code. Python 3.0 was released in 2008. It is used for web development, data science and artificial intelligence.",
 "Python is a programming language created by Guido van Rossum.", "Guido van Rossum", "Dennis Ritchie",
 ["!This language was created by Dennis Ritchie.", "Its first version was released in 1991.", "It is known for its simple and readable code.", "Version 3.0 was released in 2008.", "It is used for web development, data science and artificial intelligence."],
 "Python was created by Guido van Rossum, not by Dennis Ritchie."),
("Transistor", "computing and electronics basics", "date",
 "The transistor is a small electronic device that can amplify or switch signals. It was invented at Bell Labs in 1947 by John Bardeen, Walter Brattain and William Shockley. The three men won the Nobel Prize in Physics in 1956. Transistors replaced vacuum tubes in many devices. A modern chip can contain billions of them.",
 "It was invented at Bell Labs in 1947 by John Bardeen, Walter Brattain and William Shockley.", "1947", "1957",
 ["It is a small electronic device that can amplify or switch signals.", "!It was invented at Bell Labs in 1957.", "Its three inventors won the Nobel Prize in Physics in 1956.", "It replaced vacuum tubes in many devices.", "A modern chip can contain billions of them."],
 "It was invented in 1947, not in 1957."),
("Mars", "science", "number",
 "Mars is the fourth planet from the Sun. It is called the Red Planet because of the iron oxide on its surface. Mars has two small moons, Phobos and Deimos. A day on Mars lasts about 24 hours and 37 minutes. The highest volcano in the Solar System, Olympus Mons, is on Mars. NASA's rover Perseverance landed there in 2021.",
 "A day on Mars lasts about 24 hours and 37 minutes.", "24", "30",
 ["It is the fourth planet from the Sun.", "It is called the Red Planet because of the iron oxide on its surface.", "It has two small moons, Phobos and Deimos.", "!A day there lasts about 30 hours and 37 minutes.", "A NASA rover called Perseverance landed there in 2021."],
 "A day lasts about 24 hours and 37 minutes, not 30."),
("DNA", "science", "date",
 "DNA is the molecule that carries genetic information in living things. Its structure is a double helix. The double helix was described in 1953 by James Watson and Francis Crick, using data from Rosalind Franklin. Human DNA has about 3 billion base pairs. The Human Genome Project was completed in 2003.",
 "The double helix was described in 1953 by James Watson and Francis Crick, using data from Rosalind Franklin.", "1953", "1963",
 ["It is the molecule that carries genetic information in living things.", "Its structure is a double helix.", "!The double helix was described in 1963.", "A human has about 3 billion base pairs of this molecule.", "A project to read all human genes was completed in 2003."],
 "The double helix was described in 1953, not in 1963."),
("Seoul", "Korea", "place",
 "Seoul is the capital and largest city of South Korea. It lies on the Han River. The city was the capital of the Joseon dynasty, which began in 1392. More than 9 million people live in the city. Seoul hosted the Summer Olympic Games in 1988.",
 "It lies on the Han River.", "Han River", "Nakdong River",
 ["It is the capital and largest city of South Korea.", "!It lies on the Nakdong River.", "It was the capital of the Joseon dynasty, which began in 1392.", "More than 9 million people live there.", "It hosted the Summer Olympic Games in 1988."],
 "The city lies on the Han River, not on the Nakdong River."),
("Gyeongbokgung", "Korea", "date",
 "Gyeongbokgung is a royal palace in the capital of South Korea. It was built in 1395 by the Joseon dynasty. The palace was burned in 1592 during the Japanese invasions. It was rebuilt in 1867. Today many visitors come to see the changing of the royal guard ceremony.",
 "It was built in 1395 by the Joseon dynasty.", "1395", "1405",
 ["It is a royal palace in the capital of South Korea.", "!It was built in 1405 by the Joseon dynasty.", "It was burned in 1592 during the Japanese invasions.", "It was rebuilt in 1867.", "Today many visitors come to see the changing of the royal guard ceremony."],
 "The palace was built in 1395, not in 1405."),
("Napoleon", "France", "place",
 "Napoleon Bonaparte was a French military leader. He was born in 1769 on the island of Corsica. He crowned himself Emperor of the French in 1804. He was defeated at the Battle of Waterloo in 1815. He died in 1821 on the island of Saint Helena.",
 "He died in 1821 on the island of Saint Helena.", "Saint Helena", "Elba",
 ["He was a French military leader.", "He was born in 1769 on the island of Corsica.", "He crowned himself Emperor of the French in 1804.", "He was defeated at the Battle of Waterloo in 1815.", "!He died in 1821 on the island of Elba."],
 "He died on Saint Helena, not on Elba."),
("Louvre", "France", "date",
 "The Louvre is the largest art museum in the world. It stands in Paris, on the right bank of the Seine river. The building was a royal palace before it became a museum in 1793. The glass pyramid at the entrance was finished in 1989. The museum shows the Mona Lisa.",
 "The building was a royal palace before it became a museum in 1793.", "1793", "1783",
 ["It is the largest art museum in the world.", "It stands in Paris, on the right bank of the Seine river.", "!The building was a royal palace before it became a museum in 1783.", "Its glass pyramid was finished in 1989.", "It shows the Mona Lisa."],
 "It became a museum in 1793, not in 1783."),
("Alan Turing", "computing and electronics basics", "place",
 "Alan Turing was an English mathematician and computer scientist. He was born in London in 1912. During the Second World War he worked at Bletchley Park, where he helped to break German codes. In 1950 he proposed the Turing test, a way to test if a machine can think. He died in 1954.",
 "During the Second World War he worked at Bletchley Park, where he helped to break German codes.", "Bletchley Park", "Los Alamos",
 ["He was an English mathematician and computer scientist.", "He was born in London in 1912.", "!During the Second World War he worked at Los Alamos, where he helped to break German codes.", "In 1950 he proposed a test to check if a machine can think.", "He died in 1954."],
 "He worked at Bletchley Park, not at Los Alamos."),
("Bermuda Triangle", "famous mysteries and investigations", "person",
 "The Bermuda Triangle is an area of the Atlantic Ocean between Bermuda, Miami and Puerto Rico. Many stories say that ships and planes have disappeared there. The most famous case is Flight 19, five US Navy planes that vanished in 1945. Scientists say that the number of accidents is not higher than in other busy areas. The name was made popular by a magazine article by Vincent Gaddis in 1964.",
 "The name was made popular by a magazine article by Vincent Gaddis in 1964.", "Vincent Gaddis", "Carl Sagan",
 ["It is an area of the Atlantic Ocean near Miami and Puerto Rico.", "Many stories say that ships and planes have disappeared there.", "The most famous case is five US Navy planes that vanished in 1945.", "Scientists say that the number of accidents is not higher than in other busy areas.", "!The name was made popular by a magazine article by Carl Sagan in 1964."],
 "The name was made popular by Vincent Gaddis, not by Carl Sagan."),
("Stonehenge", "famous mysteries and investigations", "number",
 "Stonehenge is a prehistoric monument in Wiltshire, England. It consists of a ring of large standing stones. The first stage of the monument was built about 3100 BC. The tallest stones are about 7 metres high. It became a UNESCO World Heritage Site in 1986. People still gather there to watch the sunrise at midsummer.",
 "The tallest stones are about 7 metres high.", "7", "17",
 ["It is a prehistoric monument in Wiltshire, England.", "It consists of a ring of large standing stones.", "The first stage was built about 3100 BC.", "!The tallest stones are about 17 metres high.", "It became a UNESCO World Heritage Site in 1986."],
 "The tallest stones are about 7 metres high, not 17."),
]


def build():
    out = []
    for i, (title, cat, ty, article, orig_s, orig_v, false_v, clues, expl) in enumerate(RAW, 1):
        assert orig_s in article and orig_v in orig_s, title
        false_s = orig_s.replace(orig_v, false_v, 1)
        cl = [{"id": k, "text": t.lstrip("!"), "is_false": t.startswith("!")} for k, t in enumerate(clues, 1)]
        assert sum(c["is_false"] for c in cl) == 1, title
        out.append({"article": article, "case": {
            "case_id": f"demo{i:04d}", "wiki_title": title, "category": cat, "tamper_type": ty, "clues": cl,
            "original_sentence": orig_s, "false_sentence": false_s, "original_value": orig_v,
            "false_value": false_v, "explanation": expl, "briefing": ""}})
    return out


if __name__ == "__main__":
    data = build()
    CASES_FILE.write_text(json.dumps(data, indent=1, ensure_ascii=False), "utf-8")
    print("written", len(data), "cases")
