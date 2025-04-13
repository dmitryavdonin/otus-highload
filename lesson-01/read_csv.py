import csv

# Попробуем разные кодировки
encodings = ['utf-8', 'cp1251', 'latin1', 'utf-16']

for encoding in encodings:
    try:
        print(f"Trying encoding: {encoding}")
        with open('people.v2.csv', 'r', encoding=encoding) as f:
            reader = csv.reader(f)
            for i, row in enumerate(reader):
                if i >= 5:  # Читаем только первые 5 строк
                    break
                print(row)
        print("Success!")
        break
    except UnicodeDecodeError:
        print(f"Failed with encoding: {encoding}")
        continue