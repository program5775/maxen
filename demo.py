from maxen import Engine
from maxen.regeln import GENERAL, MAX, PASCH, STRASSE

FAELLE = [(3, (6, 6, 2), 1), (3, (2, 3, 5), 1), (2, (2, 3, 5), 1), (3, (1, 4, 6), 1),
          (3, (1, 4, 6), 2), (3, (6, 6, 3), 3), (2, (6, 6, 3), 2), (2, (5, 5, 3), 1)]

for n, wurf, nr in FAELLE:
    emp = Engine(wuerfe=n).empfehlung(wurf, wurf_nr=nr)
    print(f"\n== {n} Würfe erlaubt, nach Wurf {nr}: {wurf}")
    print(" ->", emp.begruendung())
    print(f"   {'nicht verl.':>11}  {'Option':45s} {'≥Max':>6} {'≥Pasch':>7} {'≥Straße':>8}")
    for b in emp.optionen[:4]:
        print(f"   {b.nutzen*100:10.1f}%  {b.option.text:45s} "
              f"{b.mindestens(MAX)*100:5.1f}% {b.mindestens(PASCH)*100:6.1f}% {b.mindestens(STRASSE)*100:7.1f}%")

for n in (1, 2, 3):
    s = Engine(wuerfe=n).startwert()
    print(f"\nVor Wurf 1, {n} Würfe:", {k: f"{v*100:.1f}%" for k, v in s.kategorien().items()})
