import psycopg2

connection = psycopg2.connect(
    dbname="ai_trading",
    user="daniyal"
)

cursor = connection.cursor()

cursor.execute("SELECT current_database(), version();")

result = cursor.fetchone()

print("Database:", result[0])
print("PostgreSQL:", result[1])

cursor.close()
connection.close()
