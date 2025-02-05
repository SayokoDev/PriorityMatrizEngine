import sqlite3
from datetime import datetime, timedelta
from tabulate import tabulate

# Configuración
DB_NAME = "tasks_pro.db"
WEIGHTS = {"impact": 3, "difficulty": 2, "time_required": 1}  # Pesos personalizables

class Database:
    def __init__(self, db_name):
        self.db_name = db_name
        self.initialize_db()

    def initialize_db(self):
        with sqlite3.connect(self.db_name) as conn:
            c = conn.cursor()
            c.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    deadline DATETIME,
                    time_required REAL,
                    difficulty INTEGER,
                    impact INTEGER,
                    completed INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()

    def execute_query(self, query, params=()):
        with sqlite3.connect(self.db_name) as conn:
            c = conn.cursor()
            c.execute(query, params)
            conn.commit()
            return c.fetchall()

class Task:
    def __init__(self, name, deadline, time_required, difficulty, impact):
        self.name = name
        self.deadline = deadline
        self.time_required = time_required
        self.difficulty = difficulty
        self.impact = impact

    def calculate_priority(self):
        now = datetime.now()
        try:
            deadline = datetime.strptime(self.deadline, "%Y-%m-%d %H:%M:%S")
            if deadline.hour == 0 and deadline.minute == 0:
                deadline = deadline.replace(hour=23, minute=59)
        except (ValueError, TypeError) as e:
            print(f"Error en formato de fecha: {e}")
            return 0.0

        time_remaining = max((deadline - now).total_seconds() / 3600, 0.1)
        norm_time_required = self.time_required / 24
        norm_time_remaining = time_remaining / 168

        score = (
            (self.impact * WEIGHTS["impact"]) +
            (self.difficulty * WEIGHTS["difficulty"]) +
            (norm_time_required * WEIGHTS["time_required"])
        ) / norm_time_remaining

        return round(score, 2)

class TaskManager:
    def __init__(self, db):
        self.db = db
        self.task_priority_map = {}  # Mapa para mantener la relación entre row_number e id

    def add_task(self, task):
        self.db.execute_query('''
            INSERT INTO tasks (name, deadline, time_required, difficulty, impact)
            VALUES (?, ?, ?, ?, ?)
        ''', (task.name, task.deadline, task.time_required, task.difficulty, task.impact))
        print("\n✅ Tarea añadida!")

    def show_tasks(self, show_completed=False):
        query = '''
            SELECT id, name, deadline, time_required, difficulty, impact, completed 
            FROM tasks 
        '''
        if not show_completed:
            query += ' WHERE completed = 0'
        
        tasks = self.db.execute_query(query)

        if not tasks:
            print("\nNo hay tareas para mostrar.")
            return

        task_list = []
        for task_data in tasks:
            task = Task(*task_data[1:6])
            priority = task.calculate_priority()
            deadline = datetime.strptime(task_data[2], "%Y-%m-%d %H:%M:%S")
            time_remaining = max((deadline - datetime.now()).total_seconds() / 3600, 0)
            feasible = "✅" if task.time_required <= time_remaining else "⚠️ IMPOSIBLE"
            completed = "✓" if task_data[6] == 1 else ""

            task_list.append([
                task_data[0], f"{task.name} {completed}", f"{time_remaining:.1f}h", 
                f"{task.time_required}h", task.difficulty, task.impact, priority, feasible
            ])

        # Ordenar por completado y prioridad
        task_list.sort(key=lambda x: (x[1].endswith("✓"), -x[6]))
        
        # Crear el mapeo de row_number a id
        self.task_priority_map = {i+1: task[0] for i, task in enumerate(task_list)}
        
        # Reemplazar el ID con row_number
        for i, task in enumerate(task_list):
            task[0] = i + 1

        headers = ["#", "Nombre", "T. Restante", "T. Requerido", "Dif", "Imp", "Prioridad", "Factible"]
        print("\n" + tabulate(task_list, headers=headers, tablefmt="grid"))

    def delete_task(self, row_number):
        task_id = self.task_priority_map.get(row_number)
        if task_id:
            self.db.execute_query("DELETE FROM tasks WHERE id = ?", (task_id,))
            print("\n🗑️ Tarea eliminada!")
        else:
            print("\n❌ Número de tarea inválido.")

    def modify_task(self, row_number, field, new_value):
        task_id = self.task_priority_map.get(row_number)
        if not task_id:
            print("\n❌ Número de tarea inválido.")
            return

        if field == "time_required":
            new_value = float(new_value)
        elif field in ["difficulty", "impact"]:
            new_value = int(new_value)

        self.db.execute_query(f"UPDATE tasks SET {field} = ? WHERE id = ?", (new_value, task_id))
        print("\n🔄 Tarea actualizada!")

    def mark_completed(self, row_number):
        task_id = self.task_priority_map.get(row_number)
        if task_id:
            self.db.execute_query("UPDATE tasks SET completed = 1 WHERE id = ?", (task_id,))
            print("\n🎉 Tarea completada!")
        else:
            print("\n❌ Número de tarea inválido.")

    def remove_expired_tasks(self):
        tasks = self.db.execute_query('''
            SELECT id, name, deadline FROM tasks WHERE completed = 0
        ''')

        now = datetime.now()
        expired_tasks = []

        for task in tasks:
            deadline = datetime.strptime(task[2], "%Y-%m-%d %H:%M:%S")
            if now > deadline:
                expired_tasks.append(task)
                self.db.execute_query("DELETE FROM tasks WHERE id = ?", (task[0],))

        for task in expired_tasks:
            print(f"\n🗑️ Tarea '{task[1]}' eliminada por haber sobrepasado el tiempo límite.")

class TaskApp:
    def __init__(self):
        self.db = Database(DB_NAME)
        self.task_manager = TaskManager(self.db)

    def menu(self):
        self.task_manager.remove_expired_tasks()
        while True:
            print("\n--- Gestor de Tareas Pro ---")
            print("1. Crear tarea")
            print("2. Mostrar tareas pendientes")
            print("3. Mostrar todas las tareas")
            print("4. Modificar tarea")
            print("5. Marcar como completada")
            print("6. Borrar tarea")
            print("7. Salir")

            choice = input("\nElige una opción: ")
            if choice == '1':
                self.create_task()
            elif choice == '2':
                self.task_manager.show_tasks(show_completed=False)
            elif choice == '3':
                self.task_manager.show_tasks(show_completed=True)
            elif choice == '4':
                self.modify_task()
            elif choice == '5':
                self.complete_task()
            elif choice == '6':
                self.delete_task()
            elif choice == '7':
                print("\n¡Hasta luego! 👋")
                break
            else:
                print("\n❌ Opción inválida.")

    def create_task(self):
        name = input("\nNombre de la tarea: ")
        while True:
            date_input = input("Fecha límite (formato ej. 15-01-2024 18:30): ")
            try:
                deadline = datetime.strptime(date_input, "%d-%m-%Y %H:%M")
                if deadline.hour == 0 and deadline.minute == 0:
                    deadline = deadline.replace(hour=23, minute=59)
                break
            except ValueError:
                print("Formato de fecha inválido. Intente nuevamente.")

        time_required = float(input("Tiempo requerido (horas): "))
        difficulty = int(input("Dificultad (1-5): "))
        impact = int(input("Impacto (1-5): "))

        task = Task(name, deadline.strftime("%Y-%m-%d %H:%M:%S"), time_required, difficulty, impact)
        self.task_manager.add_task(task)

    def modify_task(self):
        row_number = int(input("\nNúmero de la tarea a modificar: "))
        field = input("Campo a modificar (name/deadline/time_required/difficulty/impact): ")
        new_value = input("Nuevo valor: ")
        self.task_manager.modify_task(row_number, field, new_value)

    def complete_task(self):
        row_number = int(input("\nNúmero de la tarea completada: "))
        self.task_manager.mark_completed(row_number)

    def delete_task(self):
        row_number = int(input("\nNúmero de la tarea a borrar: "))
        confirmacion = input("¿Estás seguro de que quieres borrar esta tarea? (si/no): ").lower()
        if confirmacion == 'si':
            self.task_manager.delete_task(row_number)
        else:
            print("\n❌ Operación cancelada.")

if __name__ == "__main__":
    app = TaskApp()
    app.menu() 