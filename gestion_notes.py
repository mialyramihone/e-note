import sys
import sqlite3
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QMessageBox, QComboBox, QTableWidget, QTableWidgetItem,
    QSpinBox, QDoubleSpinBox, QGroupBox, QFileDialog, QTextEdit, QDialog,
    QTextBrowser
)

from PyQt5.QtGui import QPalette, QColor, QIcon 
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_pdf import PdfPages
from datetime import datetime
import os

DB_FILE = "gestion_notes.db"

class Database:
    def __init__(self, filename=DB_FILE):
        self.conn = sqlite3.connect(filename)
        self._create_tables()
        self.update_database_schema()  

    def _create_tables(self):
        cur = self.conn.cursor()
        cur.execute("PRAGMA foreign_keys = ON")
        
        cur.execute("""
        CREATE TABLE IF NOT EXISTS etudiants (
            n_inscription TEXT PRIMARY KEY,
            nom TEXT NOT NULL,
            niveau TEXT NOT NULL,
            annee INTEGER NOT NULL
        )""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS matieres (
            codeMat TEXT PRIMARY KEY,
            libelle TEXT NOT NULL,
            coef REAL NOT NULL
        )""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codeMat TEXT NOT NULL,
            n_inscription TEXT NOT NULL,
            annee INTEGER NOT NULL,
            note REAL NOT NULL,
            FOREIGN KEY(codeMat) REFERENCES matieres(codeMat) ON DELETE CASCADE,
            FOREIGN KEY(n_inscription) REFERENCES etudiants(n_inscription) ON DELETE CASCADE,
            UNIQUE(codeMat, n_inscription, annee)
        )""")
        
        cur.execute("PRAGMA foreign_keys")
        result = cur.fetchone()
        print(f"Foreign keys enabled: {result[0]}")
        
        self.conn.commit()

    def get_total_notes_count(self):
            """Retourne le nombre total de notes dans la base"""
            self._enable_foreign_keys()
            cur = self.conn.cursor()
            cur.execute("SELECT COUNT(*) FROM notes")
            return cur.fetchone()[0]

    def update_database_schema(self):
        """Mettre à jour le schéma de la base de données si nécessaire"""
        cur = self.conn.cursor()
        
        
        try:
            cur.execute("""
            SELECT sql FROM sqlite_master 
            WHERE type='table' AND name='notes'
            """)
            table_sql = cur.fetchone()[0]
            
            if "UNIQUE(codeMat, n_inscription, annee)" not in table_sql:
                
                print("Mise à jour du schéma de la table notes...")
                
                cur.execute("""
                CREATE TABLE notes_temp (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    codeMat TEXT NOT NULL,
                    n_inscription TEXT NOT NULL,
                    annee INTEGER NOT NULL,
                    note REAL NOT NULL,
                    FOREIGN KEY(codeMat) REFERENCES matieres(codeMat) ON DELETE CASCADE,
                    FOREIGN KEY(n_inscription) REFERENCES etudiants(n_inscription) ON DELETE CASCADE,
                    UNIQUE(codeMat, n_inscription, annee)
                )
                """)
                
                
                cur.execute("""
                INSERT INTO notes_temp (codeMat, n_inscription, annee, note)
                SELECT codeMat, n_inscription, annee, note
                FROM notes
                GROUP BY codeMat, n_inscription, annee
                HAVING MAX(id)  -- Garder la note la plus récente en cas de doublon
                """)
                
                cur.execute("DROP TABLE notes")
                cur.execute("ALTER TABLE notes_temp RENAME TO notes")
                
                self.conn.commit()
                print("Schéma mis à jour avec succès")
                
        except Exception as e:
            print(f"Erreur lors de la mise à jour du schéma: {e}")
            self.conn.rollback()

    def _enable_foreign_keys(self):
        self.conn.execute("PRAGMA foreign_keys = ON")

    def add_etudiant(self, n_insc, nom, niveau, annee):
        try:
            self._enable_foreign_keys()
            self.conn.execute("INSERT INTO etudiants (n_inscription, nom, niveau, annee) VALUES (?, ?, ?, ?)",
                              (n_insc, nom, niveau, annee))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def update_etudiant(self, n_insc, nom, niveau, annee):
        self._enable_foreign_keys()
        cur = self.conn.cursor()
        cur.execute("UPDATE etudiants SET nom=?, niveau=?, annee=? WHERE n_inscription=?",
                    (nom, niveau, annee, n_insc))
        self.conn.commit()
        return cur.rowcount

    def delete_etudiant(self, n_insc):
        self._enable_foreign_keys()
        cur = self.conn.cursor()
        try:
            cur.execute("SELECT COUNT(*) FROM etudiants WHERE n_inscription=?", (n_insc,))
            if cur.fetchone()[0] == 0:
                return 0, 0
            
            cur.execute("SELECT COUNT(*) FROM notes WHERE n_inscription=?", (n_insc,))
            notes_count = cur.fetchone()[0]
            
            if notes_count > 0:
                cur.execute("DELETE FROM notes WHERE n_inscription=?", (n_insc,))
            
            cur.execute("DELETE FROM etudiants WHERE n_inscription=?", (n_insc,))
            self.conn.commit()
            
            return cur.rowcount, notes_count
        except sqlite3.Error as e:
            self.conn.rollback()
            print(f"Erreur SQLite: {e}")
            raise e

    def get_etudiants(self, annee=None, niveau=None):
        self._enable_foreign_keys()
        cur = self.conn.cursor()
        q = "SELECT n_inscription, nom, niveau, annee FROM etudiants"
        params = []
        cond = []
        if annee is not None:
            cond.append("annee=?")
            params.append(annee)
        if niveau is not None and niveau != "":
            cond.append("niveau=?")
            params.append(niveau)
        if cond:
            q += " WHERE " + " AND ".join(cond)
        q += " ORDER BY n_inscription"
        cur.execute(q, params)
        return cur.fetchall()

    def find_etudiant(self, n_insc_or_nom):
        self._enable_foreign_keys()
        cur = self.conn.cursor()
        cur.execute("""SELECT n_inscription, nom, niveau, annee FROM etudiants
                       WHERE n_inscription = ? OR nom LIKE ?""",
                    (n_insc_or_nom, f"%{n_insc_or_nom}%"))
        return cur.fetchall()

    def add_matiere(self, code, libelle, coef):
        try:
            self._enable_foreign_keys()
            self.conn.execute("INSERT INTO matieres (codeMat, libelle, coef) VALUES (?, ?, ?)",
                              (code, libelle, coef))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def update_matiere(self, code, libelle, coef):
        self._enable_foreign_keys()
        cur = self.conn.cursor()
        cur.execute("UPDATE matieres SET libelle=?, coef=? WHERE codeMat=?",
                    (libelle, coef, code))
        self.conn.commit()
        return cur.rowcount

    def delete_matiere(self, code):
        self._enable_foreign_keys()
        cur = self.conn.cursor()
        try:
            cur.execute("SELECT COUNT(*) FROM matieres WHERE codeMat=?", (code,))
            if cur.fetchone()[0] == 0:
                return 0, 0
            
            cur.execute("SELECT COUNT(*) FROM notes WHERE codeMat=?", (code,))
            notes_count = cur.fetchone()[0]
            
            if notes_count > 0:
                cur.execute("DELETE FROM notes WHERE codeMat=?", (code,))
            
            cur.execute("DELETE FROM matieres WHERE codeMat=?", (code,))
            self.conn.commit()
            
            return cur.rowcount, notes_count
        except sqlite3.Error as e:
            self.conn.rollback()
            print(f"Erreur SQLite: {e}")
            raise e

    def get_matieres(self, coef_min=None, coef_max=None):
        self._enable_foreign_keys()
        cur = self.conn.cursor()
        q = "SELECT codeMat, libelle, coef FROM matieres"
        params = []
        cond = []
        if coef_min is not None:
            cond.append("coef >= ?")
            params.append(coef_min)
        if coef_max is not None:
            cond.append("coef <= ?")
            params.append(coef_max)
        if cond:
            q += " WHERE " + " AND ".join(cond)
        q += " ORDER BY codeMat"
        cur.execute(q, params)
        return cur.fetchall()

    def find_matiere(self, search_term):
        self._enable_foreign_keys()
        cur = self.conn.cursor()
        cur.execute("""SELECT codeMat, libelle, coef FROM matieres
                       WHERE codeMat LIKE ? OR libelle LIKE ?""",
                    (f"%{search_term}%", f"%{search_term}%"))
        return cur.fetchall()

    def get_matiere(self, code):
        self._enable_foreign_keys()
        cur = self.conn.cursor()
        cur.execute("SELECT codeMat, libelle, coef FROM matieres WHERE codeMat=?", (code,))
        return cur.fetchone()

    def add_note(self, codeMat, n_inscription, annee, note):
        self._enable_foreign_keys()
        cur = self.conn.cursor()
    
        cur.execute("SELECT id FROM notes WHERE codeMat=? AND n_inscription=? AND annee=?",
                (codeMat, n_inscription, annee))
        existing_note = cur.fetchone()
    
        if existing_note:
            return None  
    
        cur.execute("INSERT INTO notes (codeMat, n_inscription, annee, note) VALUES (?, ?, ?, ?)",
                (codeMat, n_inscription, annee, note))
        self.conn.commit()
        return cur.lastrowid

    def update_note(self, note_id, codeMat, n_inscription, annee, note):
        self._enable_foreign_keys()
        cur = self.conn.cursor()
        cur.execute("SELECT id FROM notes WHERE codeMat=? AND n_inscription=? AND annee=? AND id != ?",
                (codeMat, n_inscription, annee, note_id))
        existing_note = cur.fetchone()
    
        if existing_note:
            return None  
    
        cur.execute("UPDATE notes SET codeMat=?, n_inscription=?, annee=?, note=? WHERE id=?",
                    (codeMat, n_inscription, annee, note, note_id))
        self.conn.commit()
        return cur.rowcount

    def delete_note(self, note_id):
        self._enable_foreign_keys()
        cur = self.conn.cursor()
        cur.execute("DELETE FROM notes WHERE id=?", (note_id,))
        self.conn.commit()
        return cur.rowcount

    def get_notes(self, n_inscription=None, annee=None, niveau=None):
        self._enable_foreign_keys()
        cur = self.conn.cursor()
        q = """SELECT notes.id, notes.codeMat, matieres.libelle, matieres.coef,
                      notes.n_inscription, etudiants.nom, etudiants.niveau, notes.annee, notes.note
               FROM notes
               LEFT JOIN matieres ON notes.codeMat = matieres.codeMat
               LEFT JOIN etudiants ON notes.n_inscription = etudiants.n_inscription"""
        params = []
        cond = []
        if n_inscription:
            cond.append("notes.n_inscription=?")
            params.append(n_inscription)
        if annee:
            cond.append("notes.annee=?")
            params.append(annee)
        if niveau and niveau != "":
            cond.append("etudiants.niveau=?")
            params.append(niveau)
        if cond:
            q += " WHERE " + " AND ".join(cond)
        q += " ORDER BY notes.id"
        cur.execute(q, params)
        return cur.fetchall()

    def find_notes(self, search_term):
        self._enable_foreign_keys()
        cur = self.conn.cursor()
        cur.execute("""SELECT notes.id, notes.codeMat, matieres.libelle, matieres.coef,
                              notes.n_inscription, etudiants.nom, etudiants.niveau, notes.annee, notes.note
                       FROM notes
                       LEFT JOIN matieres ON notes.codeMat = matieres.codeMat
                       LEFT JOIN etudiants ON notes.n_inscription = etudiants.n_inscription
                       WHERE notes.n_inscription LIKE ? OR etudiants.nom LIKE ? OR matieres.libelle LIKE ?""",
                    (f"%{search_term}%", f"%{search_term}%", f"%{search_term}%"))
        return cur.fetchall()

    def get_notes_for_student(self, n_inscription, annee):
        self._enable_foreign_keys()
        cur = self.conn.cursor()
        cur.execute("""SELECT matieres.codeMat, matieres.libelle, matieres.coef, notes.note
                       FROM notes
                       JOIN matieres ON notes.codeMat = matieres.codeMat
                       WHERE notes.n_inscription = ? AND notes.annee = ?""",
                    (n_inscription, annee))
        return cur.fetchall()

    def calculate_average_for_student(self, n_inscription, annee):
        self._enable_foreign_keys()
        cur = self.conn.cursor()
        cur.execute("""SELECT matieres.coef, notes.note
                       FROM notes
                       JOIN matieres ON notes.codeMat = matieres.codeMat
                       WHERE notes.n_inscription = ? AND notes.annee = ?""",
                    (n_inscription, annee))
        rows = cur.fetchall()
        if not rows:
            return None
        total_coef = sum(r[0] for r in rows)
        if total_coef == 0:
            return None
        weighted_sum = sum(r[0] * r[1] for r in rows)
        moyenne = weighted_sum / total_coef
        return round(moyenne, 2), weighted_sum, total_coef

    def get_all_students_with_average(self, annee=None, niveau=None):
        self._enable_foreign_keys()
        studs = self.get_etudiants(annee=annee, niveau=niveau)
        results = []
        for n_insc, nom, niv, annee_row in studs:
            calc = self.calculate_average_for_student(n_insc, annee_row)
            moyenne = calc[0] if calc else None
            results.append((n_insc, nom, niv, annee_row, moyenne))
        return results

    def get_statistics(self, annee=None, niveau=None):
        self._enable_foreign_keys()
        students_with_avg = self.get_all_students_with_average(annee=annee, niveau=niveau)
        
        admis = 0
        redoublant = 0
        exclus = 0
        sans_notes = 0
        
        for n_insc, nom, niv, annee_row, moyenne in students_with_avg:
            if moyenne is None:
                sans_notes += 1
            elif moyenne >= 10:
                admis += 1
            elif moyenne >= 7.5:
                redoublant += 1
            else:
                exclus += 1
        
        total = len(students_with_avg)
        return {
            'admis': admis,
            'redoublant': redoublant,
            'exclus': exclus,
            'sans_notes': sans_notes,
            'total': total
        }

    def observation_from_moyenne(moyenne):
        if moyenne is None:
            return "N/A"
        if moyenne >= 10:
            return "Admis"
        if moyenne < 7.5:
            return "Exclus"
        return "Redoublant"

class MatplotlibWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.figure = plt.figure(figsize=(12, 6)) 
        self.canvas = FigureCanvas(self.figure)
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.canvas)
        self.setLayout(self.layout)

    def plot_statistics(self, statistics):
        self.figure.clear()
        
        labels = ['Admis', 'Redoublant', 'Exclus', 'Sans notes']
        sizes = [
            statistics['admis'],
            statistics['redoublant'], 
            statistics['exclus'],
            statistics['sans_notes']
        ]
        
        
        if sum(sizes) == 0:
            ax = self.figure.add_subplot(111)
            ax.text(0.5, 0.5, 'Aucune donnée disponible\nAjoutez des étudiants et des notes pour voir les statistiques',
                   horizontalalignment='center', verticalalignment='center',
                   transform=ax.transAxes, fontsize=14, color='gray')
            ax.axis('off')
            self.canvas.draw()
            return
        
        colors = ['#2ecc71', '#f39c12', '#e74c3c', '#95a5a6']
        
        
        ax1 = self.figure.add_subplot(121)
        bars = ax1.bar(labels, sizes, color=colors)
        ax1.set_title('Nombre d\'étudiants par statut')
        ax1.set_ylabel('Nombre d\'étudiants')
        ax1.set_xlabel('Statut')
        
        
        for bar, value in zip(bars, sizes):
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                    f'{value}', ha='center', va='bottom')
        
        
        ax2 = self.figure.add_subplot(122)
        explode = (0.1, 0, 0, 0)  
        ax2.pie(sizes, explode=explode, labels=labels, colors=colors, autopct='%1.1f%%',
                shadow=True, startangle=90)
        ax2.axis('equal')
        ax2.set_title('Répartition des étudiants par statut')
        
        self.figure.tight_layout()
        self.canvas.draw()

class BulletinDialog(QDialog):
    def __init__(self, html_content, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bulletin des Notes")
        self.setGeometry(100, 100, 700, 900)
        
        layout = QVBoxLayout()
        
        self.text_browser = QTextBrowser()
        self.text_browser.setHtml(html_content)
        layout.addWidget(self.text_browser)
        
        btn_layout = QHBoxLayout()
        btn_imprimer = QPushButton("Imprimer")
        btn_fermer = QPushButton("Fermer")
        
        btn_imprimer.clicked.connect(self.imprimer_bulletin)
        btn_fermer.clicked.connect(self.close)
        
        btn_layout.addWidget(btn_imprimer)
        btn_layout.addWidget(btn_fermer)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        self.html_content = html_content

    def imprimer_bulletin(self):
        try:
            printer = QPrinter(QPrinter.HighResolution)
            printer.setPageSize(QPrinter.A4)
            
            print_dialog = QPrintDialog(printer, self)
            if print_dialog.exec_() == QPrintDialog.Accepted:
                document = QTextEdit()
                document.setHtml(self.html_content)
                document.print_(printer)
                QMessageBox.information(self, "Succès", "Bulletin imprimé avec succès")
                
        except Exception as e:
            QMessageBox.warning(self, "Erreur", f"Erreur d'impression: {str(e)}")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("e-Note")
        self.setMinimumSize(1200, 800)

        self.setWindowIcon(QIcon("logo.ico"))


        self.db = Database()
        self._init_ui()
        
    def main():
        app = QApplication(sys.argv)
        
        
        if sys.platform == "win32":
            try:
                import ctypes
                myappid = 'enote.application.1.0'
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            except Exception as e:
                print(f"Note: {e}")
        
        app.setStyle('Fusion')
        
        
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(240, 240, 240))
        app.setPalette(palette)
        
        
        app.setWindowIcon(QIcon("logo.ico"))
        
        window = MainWindow()
        window.show()
        
        sys.exit(app.exec_())

        

    def _init_ui(self):
        central = QWidget()
        layout = QVBoxLayout()
        central.setLayout(layout)
        self.setCentralWidget(central)

        header = QLabel("<h1 style='color: #2c3e50;'>Gestion des Notes</h1>")
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)

        menu_layout = QHBoxLayout()
        btn_accueil = QPushButton("Accueil")
        btn_etudiants = QPushButton("Gestion des Étudiants")
        btn_matieres = QPushButton("Gestion des Matières")
        btn_notes = QPushButton("Gestion des Notes")
        btn_edition_bulletin = QPushButton("Édition Bulletin")
        btn_classement = QPushButton("Classement par ordre")

        menu_buttons = [btn_accueil, btn_etudiants, btn_matieres, btn_notes, btn_edition_bulletin, btn_classement]
        
        for button in menu_buttons:
            button.setStyleSheet("""
                QPushButton {
                    background-color: #3498db;
                    color: white;
                    font-weight: bold;
                    padding: 8px 12px;
                    border: none;
                    border-radius: 4px;
                    min-width: 120px;
                }
                QPushButton:hover {
                    background-color: #2980b9;
                }
                QPushButton:pressed {
                    background-color: #21618c;
                }
            """)

        btn_accueil.clicked.connect(self.show_accueil)
        btn_etudiants.clicked.connect(self.show_etudiants)
        btn_matieres.clicked.connect(self.show_matieres)
        btn_notes.clicked.connect(self.show_notes)
        btn_edition_bulletin.clicked.connect(self.show_edition_bulletin)
        btn_classement.clicked.connect(self.show_classement)

        for b in menu_buttons:
            menu_layout.addWidget(b)
        layout.addLayout(menu_layout)

        self.view_container = QWidget()
        self.view_layout = QVBoxLayout()
        self.view_container.setLayout(self.view_layout)
        layout.addWidget(self.view_container)

        self.show_accueil()

    def _darken_color(self, hex_color, percent):
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        
        r = max(0, min(255, r - (r * percent // 100)))
        g = max(0, min(255, g - (g * percent // 100)))
        b = max(0, min(255, b - (b * percent // 100)))
        
        return f"#{r:02x}{g:02x}{b:02x}"

    def _style_button(self, button, color, is_destructive=False):
        button.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: white;
                font-weight: bold;
                padding: 6px 12px;
                border: none;
                border-radius: 4px;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: {self._darken_color(color, 20)};
            }}
            QPushButton:pressed {{
                background-color: {self._darken_color(color, 30)};
            }}
            QPushButton:disabled {{
                background-color: #bdc3c7;
                color: #7f8c8d;
            }}
        """)

    def clear_view(self):
        while self.view_layout.count():
            child = self.view_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

   

    def show_accueil(self):
        self.clear_view()
        
        
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        container = QWidget()
        v = QVBoxLayout()
        container.setLayout(v)

        title = QLabel("<h2 style='color: #2c3e50;'>Tableau de Bord - Statistiques</h2>")
        title.setAlignment(Qt.AlignCenter)
        v.addWidget(title)


        total_etudiants = len(self.db.get_etudiants())
        
        
        niveaux = ["L1", "L2", "L3", "M1", "M2"]
        etudiants_par_niveau = {}
        for niveau in niveaux:
            etudiants = self.db.get_etudiants(niveau=niveau)
            etudiants_par_niveau[niveau] = len(etudiants)

        if total_etudiants > 0:
            niveau_group = QGroupBox("Répartition des Étudiants par Niveau")
            niveau_group.setStyleSheet("""
                QGroupBox {
                    font-weight: bold;
                    border: 2px solid #27ae60;
                    border-radius: 8px;
                    margin-top: 1ex;
                    padding-top: 10px;
                    background-color: #f8f9fa;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 8px 0 8px;
                    color: #2c3e50;
                    font-size: 14px;
                }
            """)
            niveau_layout = QHBoxLayout()
            niveau_group.setLayout(niveau_layout)

            for niveau in niveaux:
                count = etudiants_par_niveau[niveau]
                if count > 0:
                    percentage = (count / total_etudiants) * 100
                    niveau_card = QWidget()
                    niveau_card.setStyleSheet("""
                        QWidget {
                            background-color: #2c3e50;
                            border-radius: 6px;
                            padding: 8px;
                            min-width: 70px;
                        }
                    """)
                    niveau_card_layout = QVBoxLayout()
                    niveau_card.setLayout(niveau_card_layout)
                    
                    niveau_label = QLabel(niveau)
                    niveau_label.setStyleSheet("""
                        QLabel {
                            color: white;
                            font-size: 14px;
                            font-weight: bold;
                        }
                    """)
                    niveau_label.setAlignment(Qt.AlignCenter)
                    
                    count_label = QLabel(str(count))
                    count_label.setStyleSheet("""
                        QLabel {
                            color: #3498db;
                            font-size: 20px;
                            font-weight: bold;
                        }
                    """)
                    count_label.setAlignment(Qt.AlignCenter)
                    
                    percent_label = QLabel(f"{percentage:.1f}%")
                    percent_label.setStyleSheet("""
                        QLabel {
                            color: #ecf0f1;
                            font-size: 11px;
                        }
                    """)
                    percent_label.setAlignment(Qt.AlignCenter)
                    
                    niveau_card_layout.addWidget(niveau_label)
                    niveau_card_layout.addWidget(count_label)
                    niveau_card_layout.addWidget(percent_label)
                    
                    niveau_layout.addWidget(niveau_card)
                else:
                    
                    niveau_card = QWidget()
                    niveau_card.setStyleSheet("""
                        QWidget {
                            background-color: #bdc3c7;
                            border-radius: 6px;
                            padding: 8px;
                            min-width: 70px;
                        }
                    """)
                    niveau_card_layout = QVBoxLayout()
                    niveau_card.setLayout(niveau_card_layout)
                    
                    niveau_label = QLabel(niveau)
                    niveau_label.setStyleSheet("""
                        QLabel {
                            color: #7f8c8d;
                            font-size: 14px;
                            font-weight: bold;
                        }
                    """)
                    niveau_label.setAlignment(Qt.AlignCenter)
                    
                    count_label = QLabel("0")
                    count_label.setStyleSheet("""
                        QLabel {
                            color: #95a5a6;
                            font-size: 20px;
                            font-weight: bold;
                        }
                    """)
                    count_label.setAlignment(Qt.AlignCenter)
                    
                    niveau_card_layout.addWidget(niveau_label)
                    niveau_card_layout.addWidget(count_label)
                    
                    niveau_layout.addWidget(niveau_card)

            v.addWidget(niveau_group)
            v.addSpacing(20)


        filter_group = QGroupBox("Filtres pour les Graphiques")
        filter_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #9b59b6;
                border-radius: 8px;
                margin-top: 1ex;
                padding-top: 10px;
                background-color: #f8f9fa;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                color: #2c3e50;
                font-size: 14px;
            }
        """)
        
        filter_layout = QHBoxLayout()
        filter_group.setLayout(filter_layout)
        
        self.accueil_annee = QSpinBox()
        self.accueil_annee.setRange(2000, 2100)
        self.accueil_annee.setValue(datetime.now().year)
        self.accueil_niveau = QComboBox()
        self.accueil_niveau.addItems(["Tous les niveaux", "L1", "L2", "L3", "M1", "M2"])

        btn_refresh = QPushButton("Actualiser")
        btn_export_stats = QPushButton("Exporter PDF")

        self._style_button(btn_refresh, "#3498db")
        self._style_button(btn_export_stats, "#3498db")

        filter_layout.addWidget(QLabel("Année:"))
        filter_layout.addWidget(self.accueil_annee)
        filter_layout.addWidget(QLabel("Niveau:"))
        filter_layout.addWidget(self.accueil_niveau)
        filter_layout.addWidget(btn_refresh)
        filter_layout.addWidget(btn_export_stats)
        
        v.addWidget(filter_group)
        v.addSpacing(15) 


        self.stats_widget = MatplotlibWidget()
        v.addWidget(self.stats_widget)

        btn_refresh.clicked.connect(self.refresh_statistics)
        btn_export_stats.clicked.connect(self.export_statistics_pdf)

        v.addStretch()
        
        
        scroll.setWidget(container)
        self.view_layout.addWidget(scroll)
        self.refresh_statistics()


    def calculate_moyenne_generale(self):
        """Calcule la moyenne générale de tous les étudiants"""
        try:
            all_students = self.db.get_all_students_with_average()
            students_with_avg = [s for s in all_students if s[4] is not None]
            
            if not students_with_avg:
                return "N/A"
            
            total_moyenne = sum(s[4] for s in students_with_avg)
            moyenne_generale = total_moyenne / len(students_with_avg)
            return f"{moyenne_generale:.2f}"
        except:
            return "N/A"

    def refresh_statistics(self):
        annee = self.accueil_annee.value()
        niveau = self.accueil_niveau.currentText()
        if niveau == "Tous les niveaux":
            niveau = None
        
        statistics = self.db.get_statistics(annee=annee, niveau=niveau)
        self.stats_widget.plot_statistics(statistics)

    def export_statistics_pdf(self):
        annee = self.accueil_annee.value()
        niveau = self.accueil_niveau.currentText()
        
        filename, _ = QFileDialog.getSaveFileName(self, "Enregistrer les statistiques PDF", 
                                                f"statistiques_{annee}_{niveau if niveau != 'Tous les niveaux' else 'all'}.pdf", 
                                                "PDF Files (*.pdf)")
        if not filename:
            return
        
        try:
            statistics = self.db.get_statistics(annee=annee, niveau=(niveau if niveau != "Tous les niveaux" else None))
            
            
            if sum([statistics['admis'], statistics['redoublant'], statistics['exclus'], statistics['sans_notes']]) == 0:
                QMessageBox.warning(self, "Attention", "Aucune donnée disponible pour l'export.")
                return
            
            with PdfPages(filename) as pdf:
                plt.figure(figsize=(12, 6))
                
                labels = ['Admis', 'Redoublant', 'Exclus', 'Sans notes']
                sizes = [
                    statistics['admis'],
                    statistics['redoublant'], 
                    statistics['exclus'],
                    statistics['sans_notes']
                ]
                colors = ['#2ecc71', '#f39c12', '#e74c3c', '#95a5a6']
                
                
                plt.subplot(121)
                bars = plt.bar(labels, sizes, color=colors)
                plt.title('Nombre d\'étudiants par statut')
                plt.ylabel('Nombre d\'étudiants')
                plt.xlabel('Statut')
                
                for bar, value in zip(bars, sizes):
                    plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                            f'{value}', ha='center', va='bottom')
                
                
                plt.subplot(122)
                explode = (0.1, 0, 0, 0)
                plt.pie(sizes, explode=explode, labels=labels, colors=colors, autopct='%1.1f%%',
                        shadow=True, startangle=90)
                plt.axis('equal')
                plt.title('Répartition des étudiants par statut')
                
                plt.suptitle(f'Statistiques des étudiants - Année {annee}', fontsize=16, fontweight='bold')
                plt.tight_layout()
                pdf.savefig()
                plt.close()
            
            QMessageBox.information(self, "Succès", f"Statistiques exportées: {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors de l'export: {str(e)}")

    def clear_student_form(self):
        self.input_ninsc.clear()
        self.input_nom.clear()
        self.input_niveau.setCurrentIndex(0)
        self.input_annee.setValue(datetime.now().year)

    def clear_matiere_form(self):
        self.input_code.clear()
        self.input_libelle.clear()
        self.input_coef.setValue(1.0)

    def clear_note_form(self):
        self.notes_ninsc.setCurrentIndex(0)
        self.notes_annee.setValue(datetime.now().year)
        self.notes_matiere.setCurrentIndex(0)
        self.notes_val.setValue(0.0)

    def show_etudiants(self):
        self.clear_view()
        container = QWidget()
        v = QVBoxLayout()
        container.setLayout(v)

        form = QGroupBox("Ajouter / Modifier Étudiant")
        form.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #bdc3c7;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #2c3e50;
            }
        """)
        f_layout = QHBoxLayout()
        form.setLayout(f_layout)

        self.input_ninsc = QLineEdit()
        self.input_ninsc.setPlaceholderText("N° Inscription (unique)")
        self.input_nom = QLineEdit()
        self.input_nom.setPlaceholderText("Nom complet")
        self.input_niveau = QComboBox()
        self.input_niveau.addItems(["", "L1", "L2", "L3", "M1", "M2"])
        self.input_annee = QSpinBox()
        self.input_annee.setRange(2000, 2100)
        self.input_annee.setValue(datetime.now().year)

        btn_add = QPushButton("Ajouter")
        btn_update = QPushButton("Modifier")
        btn_delete = QPushButton("Supprimer")

        self._style_button(btn_add, "#3498db")
        self._style_button(btn_update, "#3498db")
        self._style_button(btn_delete, "#e74c3c", True)

        f_layout.addWidget(self.input_ninsc)
        f_layout.addWidget(self.input_nom)
        f_layout.addWidget(self.input_niveau)
        f_layout.addWidget(self.input_annee)
        f_layout.addWidget(btn_add)
        f_layout.addWidget(btn_update)
        f_layout.addWidget(btn_delete)

        v.addWidget(form)

        search_layout = QHBoxLayout()
        self.search_etudiant_input = QLineEdit()
        self.search_etudiant_input.setPlaceholderText("Rechercher par n° inscription ou nom...")
        btn_search = QPushButton("Rechercher")
        
        self._style_button(btn_search, "#3498db")
        
        search_layout.addWidget(QLabel("Recherche:"))
        search_layout.addWidget(self.search_etudiant_input)
        search_layout.addWidget(btn_search)
        v.addLayout(search_layout)

        filter_layout = QHBoxLayout()
        self.filter_annee_etud = QSpinBox()
        self.filter_annee_etud.setRange(2000, 2100)
        self.filter_annee_etud.setValue(datetime.now().year)
        self.filter_niveau_etud = QComboBox()
        self.filter_niveau_etud.addItems(["", "L1", "L2", "L3", "M1", "M2"])
        btn_filter = QPushButton("Filtrer")

        self._style_button(btn_filter, "#3498db")

        filter_layout.addWidget(QLabel("Année:"))
        filter_layout.addWidget(self.filter_annee_etud)
        filter_layout.addWidget(QLabel("Niveau:"))
        filter_layout.addWidget(self.filter_niveau_etud)
        filter_layout.addWidget(btn_filter)
        v.addLayout(filter_layout)

        self.tbl_students = QTableWidget()
        self.tbl_students.setColumnCount(4)
        self.tbl_students.setHorizontalHeaderLabels(["N° Inscription", "Nom", "Niveau", "Année"])
        self.tbl_students.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tbl_students.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tbl_students.setStyleSheet("""
            QTableWidget {
                gridline-color: #bdc3c7;
                border: 1px solid #bdc3c7;
            }
            QHeaderView::section {
                background-color: #34495e;
                color: white;
                font-weight: bold;
                padding: 6px;
                border: 1px solid #2c3e50;
            }
        """)
        v.addWidget(self.tbl_students)

        btn_add.clicked.connect(self.add_student)
        btn_update.clicked.connect(self.update_student)
        btn_delete.clicked.connect(self.delete_student)
        btn_search.clicked.connect(self.search_student)
        btn_filter.clicked.connect(self.filter_students)
        self.tbl_students.cellDoubleClicked.connect(self.fill_student_form_from_table)
        self.search_etudiant_input.returnPressed.connect(self.search_student)

        self.view_layout.addWidget(container)
        self.load_students()

    def add_student(self):
        n = self.input_ninsc.text().strip()
        nom = self.input_nom.text().strip()
        niveau = self.input_niveau.currentText()
        annee = self.input_annee.value()
        if not n or not nom or niveau == "":
            QMessageBox.warning(self, "Erreur", "Veuillez remplir tous les champs.")
            return
        ok = self.db.add_etudiant(n, nom, niveau, annee)
        if not ok:
            QMessageBox.warning(self, "Erreur", "Étudiant déjà existant.")
        else:
            QMessageBox.information(self, "Succès", "Étudiant ajouté.")
            self.clear_student_form()
            self.load_students()

    def update_student(self):
        n = self.input_ninsc.text().strip()
        nom = self.input_nom.text().strip()
        niveau = self.input_niveau.currentText()
        annee = self.input_annee.value()
        if not n:
            QMessageBox.warning(self, "Erreur", "Entrez le N° d'inscription pour modifier.")
            return
        rows = self.db.update_etudiant(n, nom, niveau, annee)
        if rows:
            QMessageBox.information(self, "Succès", "Étudiant modifié.")
            self.clear_student_form()
            self.load_students()
        else:
            QMessageBox.warning(self, "Erreur", "Étudiant non trouvé.")

    def delete_student(self):
        n = self.input_ninsc.text().strip()
        if not n:
            QMessageBox.warning(self, "Erreur", "Entrez le N° d'inscription à supprimer.")
            return
        
        reply = QMessageBox.question(self, "Confirmation de suppression",
                                   f"Voulez-vous vraiment supprimer l'étudiant {n} ?\n"
                                   "Toutes ses notes seront également supprimées.",
                                   QMessageBox.Yes | QMessageBox.No,
                                   QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                students_deleted, notes_deleted = self.db.delete_etudiant(n)
                if students_deleted:
                    message = f"Étudiant supprimé avec succès.\n"
                    if notes_deleted > 0:
                        message += f"{notes_deleted} note(s) associée(s) ont également été supprimée(s)."
                    else:
                        message += "Aucune note associée trouvée."
                    QMessageBox.information(self, "Succès", message)
                    self.clear_student_form()
                    self.load_students()
                else:
                    QMessageBox.warning(self, "Erreur", "Étudiant non trouvé.")
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Erreur lors de la suppression : {str(e)}")

    def search_student(self):
        key = self.search_etudiant_input.text().strip()
        if not key:
            self.load_students()
            return
        results = self.db.find_etudiant(key)
        self.tbl_students.setRowCount(0)
        for row in results:
            r = self.tbl_students.rowCount()
            self.tbl_students.insertRow(r)
            for c, val in enumerate(row):
                self.tbl_students.setItem(r, c, QTableWidgetItem(str(val)))

    def load_students(self):
        rows = self.db.get_etudiants()
        self.tbl_students.setRowCount(0)
        for row in rows:
            r = self.tbl_students.rowCount()
            self.tbl_students.insertRow(r)
            for c, val in enumerate(row):
                self.tbl_students.setItem(r, c, QTableWidgetItem(str(val)))

    def filter_students(self):
        annee = self.filter_annee_etud.value()
        niveau = self.filter_niveau_etud.currentText()
        if niveau == "":
            niveau = None
        rows = self.db.get_etudiants(annee=annee, niveau=niveau)
        self.tbl_students.setRowCount(0)
        for row in rows:
            r = self.tbl_students.rowCount()
            self.tbl_students.insertRow(r)
            for c, val in enumerate(row):
                self.tbl_students.setItem(r, c, QTableWidgetItem(str(val)))

    def fill_student_form_from_table(self, row, col):
        n = self.tbl_students.item(row, 0).text()
        nom = self.tbl_students.item(row, 1).text()
        niveau = self.tbl_students.item(row, 2).text()
        annee = int(self.tbl_students.item(row, 3).text())
        self.input_ninsc.setText(n)
        self.input_nom.setText(nom)
        idx = self.input_niveau.findText(niveau)
        if idx >= 0:
            self.input_niveau.setCurrentIndex(idx)
        self.input_annee.setValue(annee)

    def show_matieres(self):
        self.clear_view()
        container = QWidget()
        v = QVBoxLayout()
        container.setLayout(v)

        form = QGroupBox("Ajouter / Modifier Matière")
        form.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #bdc3c7;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #2c3e50;
            }
        """)
        f_layout = QHBoxLayout()
        form.setLayout(f_layout)

        self.input_code = QLineEdit()
        self.input_code.setPlaceholderText("Code matière (unique)")
        self.input_libelle = QLineEdit()
        self.input_libelle.setPlaceholderText("Libellé")
        self.input_coef = QDoubleSpinBox()
        self.input_coef.setRange(0.0, 100.0)
        self.input_coef.setSingleStep(0.5)
        self.input_coef.setValue(1.0)

        btn_add = QPushButton("Ajouter")
        btn_update = QPushButton("Modifier")
        btn_delete = QPushButton("Supprimer")

        self._style_button(btn_add, "#3498db")
        self._style_button(btn_update, "#3498db")
        self._style_button(btn_delete, "#e74c3c", True)

        f_layout.addWidget(self.input_code)
        f_layout.addWidget(self.input_libelle)
        f_layout.addWidget(self.input_coef)
        f_layout.addWidget(btn_add)
        f_layout.addWidget(btn_update)
        f_layout.addWidget(btn_delete)

        v.addWidget(form)

        search_layout = QHBoxLayout()
        self.search_matiere_input = QLineEdit()
        self.search_matiere_input.setPlaceholderText("Rechercher par code ou libellé...")
        btn_search_matiere = QPushButton("Rechercher")
        
        self._style_button(btn_search_matiere, "#3498db")
        
        search_layout.addWidget(QLabel("Recherche:"))
        search_layout.addWidget(self.search_matiere_input)
        search_layout.addWidget(btn_search_matiere)
        v.addLayout(search_layout)

        filter_layout = QHBoxLayout()
        self.filter_coef_min = QDoubleSpinBox()
        self.filter_coef_min.setRange(0.0, 100.0)
        self.filter_coef_min.setValue(0.0)
        self.filter_coef_min.setSingleStep(0.5)
        self.filter_coef_max = QDoubleSpinBox()
        self.filter_coef_max.setRange(0.0, 100.0)
        self.filter_coef_max.setValue(10.0)
        self.filter_coef_max.setSingleStep(0.5)
        btn_filter_matiere = QPushButton("Filtrer par coefficient")

        self._style_button(btn_filter_matiere, "#3498db")

        filter_layout.addWidget(QLabel("Coef min:"))
        filter_layout.addWidget(self.filter_coef_min)
        filter_layout.addWidget(QLabel("Coef max:"))
        filter_layout.addWidget(self.filter_coef_max)
        filter_layout.addWidget(btn_filter_matiere)
        v.addLayout(filter_layout)

        self.tbl_matieres = QTableWidget()
        self.tbl_matieres.setColumnCount(3)
        self.tbl_matieres.setHorizontalHeaderLabels(["Code", "Libellé", "Coef"])
        self.tbl_matieres.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tbl_matieres.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tbl_matieres.setStyleSheet("""
            QTableWidget {
                gridline-color: #bdc3c7;
                border: 1px solid #bdc3c7;
            }
            QHeaderView::section {
                background-color: #34495e;
                color: white;
                font-weight: bold;
                padding: 6px;
                border: 1px solid #2c3e50;
            }
        """)
        self.tbl_matieres.cellDoubleClicked.connect(self.fill_matiere_form_from_table)
        v.addWidget(self.tbl_matieres)

        btn_add.clicked.connect(self.add_matiere)
        btn_update.clicked.connect(self.update_matiere)
        btn_delete.clicked.connect(self.delete_matiere)
        btn_search_matiere.clicked.connect(self.search_matiere)
        btn_filter_matiere.clicked.connect(self.filter_matieres)
        self.search_matiere_input.returnPressed.connect(self.search_matiere)

        self.view_layout.addWidget(container)
        self.load_matieres()

    def add_matiere(self):
        code = self.input_code.text().strip()
        lib = self.input_libelle.text().strip()
        coef = float(self.input_coef.value())
        if not code or not lib:
            QMessageBox.warning(self, "Erreur", "Remplir tous les champs.")
            return
        ok = self.db.add_matiere(code, lib, coef)
        if not ok:
            QMessageBox.warning(self, "Erreur", "Matière déjà existante.")
        else:
            QMessageBox.information(self, "Succès", "Matière ajoutée.")
            self.clear_matiere_form()
            self.load_matieres()

    def update_matiere(self):
        code = self.input_code.text().strip()
        lib = self.input_libelle.text().strip()
        coef = float(self.input_coef.value())
        if not code:
            QMessageBox.warning(self, "Erreur", "Entrez le code de la matière.")
            return
        rows = self.db.update_matiere(code, lib, coef)
        if rows:
            QMessageBox.information(self, "Succès", "Matière modifiée.")
            self.clear_matiere_form()
            self.load_matieres()
        else:
            QMessageBox.warning(self, "Erreur", "Matière non trouvée.")

    def delete_matiere(self):
        code = self.input_code.text().strip()
        if not code:
            QMessageBox.warning(self, "Erreur", "Entrez le code de la matière à supprimer.")
            return
        
        reply = QMessageBox.question(self, "Confirmation de suppression",
                                   f"Voulez-vous vraiment supprimer la matière {code} ?\n"
                                   "Toutes les notes associées à cette matière seront également supprimées.",
                                   QMessageBox.Yes | QMessageBox.No,
                                   QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                matieres_deleted, notes_deleted = self.db.delete_matiere(code)
                if matieres_deleted:
                    message = f"Matière supprimée avec succès.\n"
                    if notes_deleted > 0:
                        message += f"{notes_deleted} note(s) associée(s) ont également été supprimée(s)."
                    else:
                        message += "Aucune note associée trouvée."
                    QMessageBox.information(self, "Succès", message)
                    self.clear_matiere_form()
                    self.load_matieres()
                else:
                    QMessageBox.warning(self, "Erreur", "Matière non trouvée.")
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Erreur lors de la suppression : {str(e)}")

    def search_matiere(self):
        key = self.search_matiere_input.text().strip()
        if not key:
            self.load_matieres()
            return
        results = self.db.find_matiere(key)
        self.tbl_matieres.setRowCount(0)
        for row in results:
            r = self.tbl_matieres.rowCount()
            self.tbl_matieres.insertRow(r)
            for c, val in enumerate(row):
                self.tbl_matieres.setItem(r, c, QTableWidgetItem(str(val)))

    def filter_matieres(self):
        coef_min = self.filter_coef_min.value()
        coef_max = self.filter_coef_max.value()
        if coef_min == 0.0 and coef_max == 100.0:
            self.load_matieres()
            return
        rows = self.db.get_matieres(coef_min=coef_min, coef_max=coef_max)
        self.tbl_matieres.setRowCount(0)
        for row in rows:
            r = self.tbl_matieres.rowCount()
            self.tbl_matieres.insertRow(r)
            for c, val in enumerate(row):
                self.tbl_matieres.setItem(r, c, QTableWidgetItem(str(val)))

    def load_matieres(self):
        rows = self.db.get_matieres()
        self.tbl_matieres.setRowCount(0)
        for row in rows:
            r = self.tbl_matieres.rowCount()
            self.tbl_matieres.insertRow(r)
            for c, val in enumerate(row):
                self.tbl_matieres.setItem(r, c, QTableWidgetItem(str(val)))

    def fill_matiere_form_from_table(self, row, col):
        code = self.tbl_matieres.item(row, 0).text()
        libelle = self.tbl_matieres.item(row, 1).text()
        coef = float(self.tbl_matieres.item(row, 2).text())
        self.input_code.setText(code)
        self.input_libelle.setText(libelle)
        self.input_coef.setValue(coef)

    def show_notes(self):
        self.clear_view()
        container = QWidget()
        v = QVBoxLayout()
        container.setLayout(v)

        form = QGroupBox("Ajouter / Modifier Note")
        form.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #bdc3c7;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #2c3e50;
            }
        """)
        f_layout = QHBoxLayout()
        form.setLayout(f_layout)

        self.notes_ninsc = QComboBox()
        self.notes_ninsc.setEditable(True)
        self.notes_ninsc.setInsertPolicy(QComboBox.NoInsert)
        self.notes_annee = QSpinBox()
        self.notes_annee.setRange(2000, 2100)
        self.notes_annee.setValue(datetime.now().year)
        self.notes_matiere = QComboBox()
        self.notes_val = QDoubleSpinBox()
        self.notes_val.setRange(0.0, 20.0)
        self.notes_val.setSingleStep(0.5)
        self.notes_val.setValue(0.0)

        btn_add_note = QPushButton("Ajouter")
        btn_update_note = QPushButton("Modifier")
        btn_delete_note = QPushButton("Supprimer")

        self._style_button(btn_add_note, "#3498db")
        self._style_button(btn_update_note, "#3498db")
        self._style_button(btn_delete_note, "#e74c3c", True)

        f_layout.addWidget(QLabel("Étudiant:"))
        f_layout.addWidget(self.notes_ninsc)
        f_layout.addWidget(QLabel("Année:"))
        f_layout.addWidget(self.notes_annee)
        f_layout.addWidget(QLabel("Matière:"))
        f_layout.addWidget(self.notes_matiere)
        f_layout.addWidget(QLabel("Note:"))
        f_layout.addWidget(self.notes_val)
        f_layout.addWidget(btn_add_note)
        f_layout.addWidget(btn_update_note)
        f_layout.addWidget(btn_delete_note)

        v.addWidget(form)

        search_layout = QHBoxLayout()
        self.search_notes_input = QLineEdit()
        self.search_notes_input.setPlaceholderText("Rechercher par étudiant, matière...")
        btn_search_notes = QPushButton("Rechercher")
        
        self._style_button(btn_search_notes, "#3498db")
        
        search_layout.addWidget(QLabel("Recherche:"))
        search_layout.addWidget(self.search_notes_input)
        search_layout.addWidget(btn_search_notes)
        v.addLayout(search_layout)

        filter_layout = QHBoxLayout()
        self.filter_notes_annee = QSpinBox()
        self.filter_notes_annee.setRange(2000, 2100)
        self.filter_notes_annee.setValue(datetime.now().year)
        self.filter_notes_niveau = QComboBox()
        self.filter_notes_niveau.addItems(["", "L1", "L2", "L3", "M1", "M2"])
        btn_filter_notes = QPushButton("Filtrer")

        self._style_button(btn_filter_notes, "#3498db")

        filter_layout.addWidget(QLabel("Année:"))
        filter_layout.addWidget(self.filter_notes_annee)
        filter_layout.addWidget(QLabel("Niveau:"))
        filter_layout.addWidget(self.filter_notes_niveau)
        filter_layout.addWidget(btn_filter_notes)
        v.addLayout(filter_layout)

        self.tbl_notes = QTableWidget()
        self.tbl_notes.setColumnCount(6)
        self.tbl_notes.setHorizontalHeaderLabels(["ID", "Étudiant", "Matière", "Coef", "Année", "Note"])
        self.tbl_notes.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tbl_notes.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tbl_notes.setStyleSheet("""
            QTableWidget {
                gridline-color: #bdc3c7;
                border: 1px solid #bdc3c7;
            }
            QHeaderView::section {
                background-color: #34495e;
                color: white;
                font-weight: bold;
                padding: 6px;
                border: 1px solid #2c3e50;
            }
        """)
        self.tbl_notes.cellDoubleClicked.connect(self.fill_note_form_from_table)
        v.addWidget(self.tbl_notes)

        btn_add_note.clicked.connect(self.add_note)
        btn_update_note.clicked.connect(self.update_note)
        btn_delete_note.clicked.connect(self.delete_note)
        btn_search_notes.clicked.connect(self.search_notes)
        btn_filter_notes.clicked.connect(self.filter_notes)
        self.search_notes_input.returnPressed.connect(self.search_notes)

        self.view_layout.addWidget(container)
        self.load_notes_combos()
        self.load_notes()

    def load_notes_combos(self):
        self.notes_ninsc.clear()
        self.notes_matiere.clear()
        
        etudiants = self.db.get_etudiants()
        for n_insc, nom, niveau, annee in etudiants:
            self.notes_ninsc.addItem(f"{n_insc} - {nom}", n_insc)
        
        matieres = self.db.get_matieres()
        for code, libelle, coef in matieres:
            self.notes_matiere.addItem(f"{code} - {libelle}", code)

    def add_note(self):
        if self.notes_ninsc.currentIndex() < 0 or self.notes_matiere.currentIndex() < 0:
            QMessageBox.warning(self, "Erreur", "Sélectionnez un étudiant et une matière.")
            return
        
        n_insc = self.notes_ninsc.currentData()
        codeMat = self.notes_matiere.currentData()
        annee = self.notes_annee.value()
        note = self.notes_val.value()
        
        try:
            note_id = self.db.add_note(codeMat, n_insc, annee, note)
            if note_id is None:
                QMessageBox.warning(self, "Erreur", "Cet étudiant a déjà une note dans cette matière pour cette année.")
            else:
                QMessageBox.information(self, "Succès", f"Note ajoutée (ID: {note_id}).")
                self.clear_note_form()
                self.load_notes()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors de l'ajout : {str(e)}")

    def update_note(self):
        current_row = self.tbl_notes.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Erreur", "Sélectionnez une note à modifier.")
            return
        
        note_id = int(self.tbl_notes.item(current_row, 0).text())
        n_insc = self.notes_ninsc.currentData()
        codeMat = self.notes_matiere.currentData()
        annee = self.notes_annee.value()
        new_note = self.notes_val.value()
        
        rows = self.db.update_note(note_id, codeMat, n_insc, annee, new_note)
        if rows is None:
            QMessageBox.warning(self, "Erreur", "Cet étudiant a déjà une autre note dans cette matière pour cette année.")
        elif rows:
            QMessageBox.information(self, "Succès", "Note modifiée.")
            self.clear_note_form()
            self.load_notes()
        else:
            QMessageBox.warning(self, "Erreur", "Erreur lors de la modification.")

    def fill_note_form_from_table(self, row, col):
        note_id = int(self.tbl_notes.item(row, 0).text())
        etudiant_text = self.tbl_notes.item(row, 1).text()
        matiere_text = self.tbl_notes.item(row, 2).text()
        annee = int(self.tbl_notes.item(row, 4).text())
        note = float(self.tbl_notes.item(row, 5).text())
        
        # Extraire le numéro d'inscription du texte
        n_insc = etudiant_text.split(' - ')[0]
        # Extraire le code matière du texte
        code_matiere = matiere_text.split(' - ')[0]
        
        
        idx_etudiant = self.notes_ninsc.findData(n_insc)
        if idx_etudiant >= 0:
            self.notes_ninsc.setCurrentIndex(idx_etudiant)
        
        idx_matiere = self.notes_matiere.findData(code_matiere)
        if idx_matiere >= 0:
            self.notes_matiere.setCurrentIndex(idx_matiere)
        
        self.notes_annee.setValue(annee)
        self.notes_val.setValue(note)
        
        
        self.current_note_id = note_id

    def delete_note(self):
        current_row = self.tbl_notes.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Erreur", "Sélectionnez une note à supprimer.")
            return
        
        note_id = int(self.tbl_notes.item(current_row, 0).text())
        
        reply = QMessageBox.question(self, "Confirmation de suppression",
                                   f"Voulez-vous vraiment supprimer cette note ?",
                                   QMessageBox.Yes | QMessageBox.No,
                                   QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            rows = self.db.delete_note(note_id)
            if rows:
                QMessageBox.information(self, "Succès", "Note supprimée.")
                self.clear_note_form()
                self.load_notes()
            else:
                QMessageBox.warning(self, "Erreur", "Erreur lors de la suppression.")

    def search_notes(self):
        key = self.search_notes_input.text().strip()
        if not key:
            self.load_notes()
            return
        results = self.db.find_notes(key)
        self.tbl_notes.setRowCount(0)
        for row in results:
            r = self.tbl_notes.rowCount()
            self.tbl_notes.insertRow(r)
            self.tbl_notes.setItem(r, 0, QTableWidgetItem(str(row[0])))
            self.tbl_notes.setItem(r, 1, QTableWidgetItem(f"{row[4]} - {row[5]}"))
            self.tbl_notes.setItem(r, 2, QTableWidgetItem(f"{row[1]} - {row[2]}"))
            self.tbl_notes.setItem(r, 3, QTableWidgetItem(str(row[3])))
            self.tbl_notes.setItem(r, 4, QTableWidgetItem(str(row[7])))
            self.tbl_notes.setItem(r, 5, QTableWidgetItem(str(row[8])))

    def filter_notes(self):
        annee = self.filter_notes_annee.value()
        niveau = self.filter_notes_niveau.currentText()
        if niveau == "":
            niveau = None
        rows = self.db.get_notes(annee=annee, niveau=niveau)
        self.tbl_notes.setRowCount(0)
        for row in rows:
            r = self.tbl_notes.rowCount()
            self.tbl_notes.insertRow(r)
            self.tbl_notes.setItem(r, 0, QTableWidgetItem(str(row[0])))
            self.tbl_notes.setItem(r, 1, QTableWidgetItem(f"{row[4]} - {row[5]}"))
            self.tbl_notes.setItem(r, 2, QTableWidgetItem(f"{row[1]} - {row[2]}"))
            self.tbl_notes.setItem(r, 3, QTableWidgetItem(str(row[3])))
            self.tbl_notes.setItem(r, 4, QTableWidgetItem(str(row[7])))
            self.tbl_notes.setItem(r, 5, QTableWidgetItem(str(row[8])))

    def load_notes(self):
        rows = self.db.get_notes()
        self.tbl_notes.setRowCount(0)
        for row in rows:
            r = self.tbl_notes.rowCount()
            self.tbl_notes.insertRow(r)
            self.tbl_notes.setItem(r, 0, QTableWidgetItem(str(row[0])))
            self.tbl_notes.setItem(r, 1, QTableWidgetItem(f"{row[4]} - {row[5]}"))
            self.tbl_notes.setItem(r, 2, QTableWidgetItem(f"{row[1]} - {row[2]}"))
            self.tbl_notes.setItem(r, 3, QTableWidgetItem(str(row[3])))
            self.tbl_notes.setItem(r, 4, QTableWidgetItem(str(row[7])))
            self.tbl_notes.setItem(r, 5, QTableWidgetItem(str(row[8])))

    def fill_note_form_from_table(self, row, col):
        note_id = int(self.tbl_notes.item(row, 0).text())
        etudiant_text = self.tbl_notes.item(row, 1).text()
        matiere_text = self.tbl_notes.item(row, 2).text()
        annee = int(self.tbl_notes.item(row, 4).text())
        note = float(self.tbl_notes.item(row, 5).text())
        
        
        n_insc = etudiant_text.split(' - ')[0]
        
        code_matiere = matiere_text.split(' - ')[0]
        
        
        idx_etudiant = self.notes_ninsc.findData(n_insc)
        if idx_etudiant >= 0:
            self.notes_ninsc.setCurrentIndex(idx_etudiant)
        
        idx_matiere = self.notes_matiere.findData(code_matiere)
        if idx_matiere >= 0:
            self.notes_matiere.setCurrentIndex(idx_matiere)
        
        self.notes_annee.setValue(annee)
        self.notes_val.setValue(note)

    def show_edition_bulletin(self):
        self.clear_view()
        container = QWidget()
        v = QVBoxLayout()
        container.setLayout(v)

        title = QLabel("<h2 style='color: #2c3e50;'>Édition des Bulletins</h2>")
        title.setAlignment(Qt.AlignCenter)
        v.addWidget(title)

        form_layout = QHBoxLayout()
        
        self.bulletin_ninsc = QComboBox()
        self.bulletin_ninsc.setEditable(True)
        self.bulletin_ninsc.setInsertPolicy(QComboBox.NoInsert)
        self.bulletin_annee = QSpinBox()
        self.bulletin_annee.setRange(2000, 2100)
        self.bulletin_annee.setValue(datetime.now().year)

        btn_generer = QPushButton("Générer Bulletin")
        btn_imprimer = QPushButton("Imprimer Bulletin")
        
        self._style_button(btn_generer, "#3498db")
        self._style_button(btn_imprimer, "#3498db")

        form_layout.addWidget(QLabel("Étudiant:"))
        form_layout.addWidget(self.bulletin_ninsc)
        form_layout.addWidget(QLabel("Année:"))
        form_layout.addWidget(self.bulletin_annee)
        form_layout.addWidget(btn_generer)
        form_layout.addWidget(btn_imprimer)

        v.addLayout(form_layout)


        self.tbl_bulletin = QTableWidget()
        self.tbl_bulletin.setColumnCount(4)
        self.tbl_bulletin.setHorizontalHeaderLabels(["Matière", "Coefficient", "Note", "Note pondérée"])
        self.tbl_bulletin.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tbl_bulletin.setStyleSheet("""
            QTableWidget {
                gridline-color: #bdc3c7;
                border: 1px solid #bdc3c7;
            }
            QHeaderView::section {
                background-color: #34495e;
                color: white;
                font-weight: bold;
                padding: 6px;
                border: 1px solid #2c3e50;
            }
        """)
        v.addWidget(self.tbl_bulletin)


        info_layout = QHBoxLayout()
        self.lbl_moyenne = QLabel("Moyenne: -")
        self.lbl_observation = QLabel("Observation: -")
        self.lbl_moyenne.setStyleSheet("font-weight: bold; font-size: 14px; color: #2c3e50;")
        self.lbl_observation.setStyleSheet("font-weight: bold; font-size: 14px; color: #2c3e50;")
        
        info_layout.addWidget(self.lbl_moyenne)
        info_layout.addWidget(self.lbl_observation)
        info_layout.addStretch()
        
        v.addLayout(info_layout)

        btn_generer.clicked.connect(self.generer_bulletin)
        btn_imprimer.clicked.connect(self.imprimer_bulletin)

        self.view_layout.addWidget(container)
        self.load_bulletin_combos()

    def load_bulletin_combos(self):
        self.bulletin_ninsc.clear()
        etudiants = self.db.get_etudiants()
        for n_insc, nom, niveau, annee in etudiants:
            self.bulletin_ninsc.addItem(f"{n_insc} - {nom}", n_insc)

    def observation_from_moyenne(self, moyenne):
            if moyenne is None:
                return "N/A"
            if moyenne >= 10:
                return "Admis"
            if moyenne < 7.5:
                return "Exclus"
            return "Redoublant"
    
    def generer_bulletin(self):
        if self.bulletin_ninsc.currentIndex() < 0:
            QMessageBox.warning(self, "Erreur", "Sélectionnez un étudiant.")
            return
        
        n_insc = self.bulletin_ninsc.currentData()
        annee = self.bulletin_annee.value()
        
        notes = self.db.get_notes_for_student(n_insc, annee)
        moyenne_data = self.db.calculate_average_for_student(n_insc, annee)
        
        self.tbl_bulletin.setRowCount(0)
        total_coef = 0
        total_notes_ponderees = 0
        
        for code, libelle, coef, note in notes:
            r = self.tbl_bulletin.rowCount()
            self.tbl_bulletin.insertRow(r)
            self.tbl_bulletin.setItem(r, 0, QTableWidgetItem(f"{code} - {libelle}"))
            self.tbl_bulletin.setItem(r, 1, QTableWidgetItem(str(coef)))
            self.tbl_bulletin.setItem(r, 2, QTableWidgetItem(str(note)))
            self.tbl_bulletin.setItem(r, 3, QTableWidgetItem(str(round(note * coef, 2))))
            
            total_coef += coef
            total_notes_ponderees += note * coef
        
        if moyenne_data:
            moyenne, weighted_sum, total_coef_calc = moyenne_data
            self.lbl_moyenne.setText(f"Moyenne: {moyenne}/20")
            observation = self.observation_from_moyenne(moyenne)  
            self.lbl_observation.setText(f"Observation: {observation}")
            
            r = self.tbl_bulletin.rowCount()
            self.tbl_bulletin.insertRow(r)
            self.tbl_bulletin.setItem(r, 0, QTableWidgetItem("TOTAL"))
            self.tbl_bulletin.setItem(r, 1, QTableWidgetItem(str(total_coef)))
            self.tbl_bulletin.setItem(r, 2, QTableWidgetItem(""))
            self.tbl_bulletin.setItem(r, 3, QTableWidgetItem(str(round(weighted_sum, 2))))
            
            r = self.tbl_bulletin.rowCount()
            self.tbl_bulletin.insertRow(r)
            self.tbl_bulletin.setItem(r, 0, QTableWidgetItem("MOYENNE"))
            self.tbl_bulletin.setItem(r, 1, QTableWidgetItem(""))
            self.tbl_bulletin.setItem(r, 2, QTableWidgetItem(""))
            self.tbl_bulletin.setItem(r, 3, QTableWidgetItem(str(moyenne)))
        else:
            self.lbl_moyenne.setText("Moyenne: Aucune note")
            self.lbl_observation.setText("Observation: N/A")
    
    def generate_bulletin_html(self, n_insc, nom, niveau, annee, notes, moyenne_data):
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Bulletin de Notes</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ text-align: center; border-bottom: 2px solid #333; padding-bottom: 10px; margin-bottom: 20px; }}
                .student-info {{ margin-bottom: 20px; }}
                .table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
                .table th, .table td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                .table th {{ background-color: #f2f2f2; font-weight: bold; }}
                .summary {{ margin-top: 20px; padding: 10px; background-color: #f9f9f9; border-radius: 5px; }}
                .footer {{ margin-top: 30px; text-align: center; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>BULLETIN DE NOTES</h1>
                <h2>Année Universitaire {annee}</h2>
            </div>
            
            <div class="student-info">
                <p><strong>Numéro d'inscription:</strong> {n_insc}</p>
                <p><strong>Nom:</strong> {nom}</p>
                <p><strong>Niveau:</strong> {niveau}</p>
                <p><strong>Année:</strong> {annee}</p>
            </div>
        """
        
        if notes:
            html += """
            <table class="table">
                <thead>
                    <tr>
                        <th>Matière</th>
                        <th>Coefficient</th>
                        <th>Note</th>
                        <th>Note pondérée</th>
                    </tr>
                </thead>
                <tbody>
            """
            
            total_coef = 0
            total_notes_ponderees = 0
            
            for code, libelle, coef, note in notes:
                note_ponderee = note * coef
                total_coef += coef
                total_notes_ponderees += note_ponderee
                
                html += f"""
                    <tr>
                        <td>{code} - {libelle}</td>
                        <td>{coef}</td>
                        <td>{note}/20</td>
                        <td>{note_ponderee:.2f}</td>
                    </tr>
                """
            
            html += f"""
                </tbody>
                <tfoot>
                    <tr style="font-weight: bold;">
                        <td>TOTAL</td>
                        <td>{total_coef}</td>
                        <td></td>
                        <td>{total_notes_ponderees:.2f}</td>
                    </tr>
            """
            
            if moyenne_data:
                moyenne, weighted_sum, total_coef_calc = moyenne_data
                observation = self.observation_from_moyenne(moyenne) 
                
                html += f"""
                    <tr style="font-weight: bold; background-color: #e8f4f8;">
                        <td>MOYENNE GÉNÉRALE</td>
                        <td></td>
                        <td></td>
                        <td>{moyenne}/20</td>
                    </tr>
                </tfoot>
            </table>
            
            <div class="summary">
                <p><strong>Moyenne générale:</strong> {moyenne}/20</p>
                <p><strong>Observation:</strong> {observation}</p>
                <p><strong>Date d'édition:</strong> {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
            </div>
                """
            else:
                html += """
                </tfoot>
            </table>
            
            <div class="summary">
                <p><strong>Moyenne générale:</strong> Non calculable</p>
                <p><strong>Observation:</strong> N/A</p>
            </div>
                """
        else:
            html += """
            <div class="summary">
                <p><strong>Aucune note enregistrée pour cette année.</strong></p>
            </div>
            """
        
        html += """
            <div class="footer" style="margin-top: 40px; text-align: center; border-top: 1px solid #ddd; padding-top: 15px;">
                <p style="color: #666; font-size: 12px; margin: 0;">
                    <strong>e-NOTE</strong> - application gestion des notes<br>
                    Bulletin généré le {}
                </p>
            </div>
        </body>
        </html>
        """.format(datetime.now().strftime('%d/%m/%Y à %H:%M'))
    

    def imprimer_bulletin(self):
        if self.bulletin_ninsc.currentIndex() < 0:
            QMessageBox.warning(self, "Erreur", "Sélectionnez un étudiant.")
            return
        
        n_insc = self.bulletin_ninsc.currentData()
        annee = self.bulletin_annee.value()
        
        
        etudiant_info = self.db.find_etudiant(n_insc)
        if not etudiant_info:
            QMessageBox.warning(self, "Erreur", "Étudiant non trouvé.")
            return
        
        n_insc, nom, niveau, annee_etud = etudiant_info[0]
        
        
        notes = self.db.get_notes_for_student(n_insc, annee)
        moyenne_data = self.db.calculate_average_for_student(n_insc, annee)
        
        
        html_content = self.generate_bulletin_html(n_insc, nom, niveau, annee, notes, moyenne_data)
        
        
        dialog = BulletinDialog(html_content, self)
        dialog.exec_()

    def generate_bulletin_html(self, n_insc, nom, niveau, annee, notes, moyenne_data):
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Bulletin de Notes</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ text-align: center; border-bottom: 2px solid #333; padding-bottom: 10px; margin-bottom: 20px; }}
                .student-info {{ margin-bottom: 20px; }}
                .table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
                .table th, .table td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                .table th {{ background-color: #f2f2f2; font-weight: bold; }}
                .summary {{ margin-top: 20px; padding: 10px; background-color: #f9f9f9; border-radius: 5px; }}
                .footer {{ margin-top: 30px; text-align: center; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>BULLETIN DE NOTES</h1>
                <h2>Année Universitaire {annee}</h2>
            </div>
            
            <div class="student-info">
                <p><strong>Numéro d'inscription:</strong> {n_insc}</p>
                <p><strong>Nom:</strong> {nom}</p>
                <p><strong>Niveau:</strong> {niveau}</p>
                <p><strong>Année:</strong> {annee}</p>
            </div>
        """
        
        if notes:
            html += """
            <table class="table">
                <thead>
                    <tr>
                        <th>Matière</th>
                        <th>Coefficient</th>
                        <th>Note</th>
                        <th>Note pondérée</th>
                    </tr>
                </thead>
                <tbody>
            """
            
            total_coef = 0
            total_notes_ponderees = 0
            
            for code, libelle, coef, note in notes:
                note_ponderee = note * coef
                total_coef += coef
                total_notes_ponderees += note_ponderee
                
                html += f"""
                    <tr>
                        <td>{code} - {libelle}</td>
                        <td>{coef}</td>
                        <td>{note}/20</td>
                        <td>{note_ponderee:.2f}</td>
                    </tr>
                """
            
            html += f"""
                </tbody>
                <tfoot>
                    <tr style="font-weight: bold;">
                        <td>TOTAL</td>
                        <td>{total_coef}</td>
                        <td></td>
                        <td>{total_notes_ponderees:.2f}</td>
                    </tr>
            """
            
            if moyenne_data:
                moyenne, weighted_sum, total_coef_calc = moyenne_data
                observation = self.observation_from_moyenne(moyenne) 
                
                html += f"""
                    <tr style="font-weight: bold; background-color: #e8f4f8;">
                        <td>MOYENNE GÉNÉRALE</td>
                        <td></td>
                        <td></td>
                        <td>{moyenne}/20</td>
                    </tr>
                </tfoot>
            </table>
            
            <div class="summary">
                <p><strong>Moyenne générale:</strong> {moyenne}/20</p>
                <p><strong>Observation:</strong> {observation}</p>
                <p><strong>Date d'édition:</strong> {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
            </div>
                """
            else:
                html += """
                </tfoot>
            </table>
            
            <div class="summary">
                <p><strong>Moyenne générale:</strong> Non calculable</p>
                <p><strong>Observation:</strong> N/A</p>
            </div>
                """
        else:
            html += """
            <div class="summary">
                <p><strong>Aucune note enregistrée pour cette année.</strong></p>
            </div>
            """
        
        html += """
            <div class="footer">
                <p>© {} E-note - Tous droits réservés</p>
            </div>
        </body>
        </html>
        """.format(datetime.now().year)
        
        return html

    def show_classement(self):
        self.clear_view()
        container = QWidget()
        v = QVBoxLayout()
        container.setLayout(v)

        title = QLabel("<h2 style='color: #2c3e50;'>Classement des Étudiants</h2>")
        title.setAlignment(Qt.AlignCenter)
        v.addWidget(title)

        filter_layout = QHBoxLayout()
        self.classement_annee = QSpinBox()
        self.classement_annee.setRange(2000, 2100)
        self.classement_annee.setValue(datetime.now().year)
        self.classement_niveau = QComboBox()
        self.classement_niveau.addItems(["Tous les niveaux", "L1", "L2", "L3", "M1", "M2"])

        btn_generer = QPushButton("Générer Classement")
        btn_export_classement = QPushButton("Exporter Classement")
        
        self._style_button(btn_generer, "#3498db")
        self._style_button(btn_export_classement, "#3498db")

        filter_layout.addWidget(QLabel("Année:"))
        filter_layout.addWidget(self.classement_annee)
        filter_layout.addWidget(QLabel("Niveau:"))
        filter_layout.addWidget(self.classement_niveau)
        filter_layout.addWidget(btn_generer)
        filter_layout.addWidget(btn_export_classement)
        v.addLayout(filter_layout)

        self.tbl_classement = QTableWidget()
        self.tbl_classement.setColumnCount(6)
        self.tbl_classement.setHorizontalHeaderLabels(["Rang", "N° Inscription", "Nom", "Niveau", "Année", "Moyenne"])
        self.tbl_classement.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tbl_classement.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tbl_classement.setStyleSheet("""
            QTableWidget {
                gridline-color: #bdc3c7;
                border: 1px solid #bdc3c7;
            }
            QHeaderView::section {
                background-color: #34495e;
                color: white;
                font-weight: bold;
                padding: 6px;
                border: 1px solid #2c3e50;
            }
        """)
        v.addWidget(self.tbl_classement)

        btn_generer.clicked.connect(self.generer_classement)
        btn_export_classement.clicked.connect(self.export_classement)

        self.view_layout.addWidget(container)
        self.generer_classement()

    def generer_classement(self):
        annee = self.classement_annee.value()
        niveau = self.classement_niveau.currentText()
        if niveau == "Tous les niveaux":
            niveau = None
        
        students_with_avg = self.db.get_all_students_with_average(annee=annee, niveau=niveau)
        
        
        students_with_avg = [s for s in students_with_avg if s[4] is not None]
        
        
        students_with_avg.sort(key=lambda x: x[4] if x[4] is not None else -1, reverse=True)
        
        self.tbl_classement.setRowCount(0)
        
        for rang, (n_insc, nom, niv, annee_etud, moyenne) in enumerate(students_with_avg, 1):
            r = self.tbl_classement.rowCount()
            self.tbl_classement.insertRow(r)
            
            self.tbl_classement.setItem(r, 0, QTableWidgetItem(str(rang)))
            self.tbl_classement.setItem(r, 1, QTableWidgetItem(n_insc))
            self.tbl_classement.setItem(r, 2, QTableWidgetItem(nom))
            self.tbl_classement.setItem(r, 3, QTableWidgetItem(niv))
            self.tbl_classement.setItem(r, 4, QTableWidgetItem(str(annee_etud)))
            self.tbl_classement.setItem(r, 5, QTableWidgetItem(str(moyenne) if moyenne is not None else "N/A"))
            
            
            if rang == 1:
                
                for c in range(6):
                    self.tbl_classement.item(r, c).setBackground(QColor(255, 215, 0))
            elif rang == 2:
                
                for c in range(6):
                    self.tbl_classement.item(r, c).setBackground(QColor(192, 192, 192))
            elif rang == 3:
                
                for c in range(6):
                    self.tbl_classement.item(r, c).setBackground(QColor(205, 127, 50))

    def export_classement(self):
        annee = self.classement_annee.value()
        niveau = self.classement_niveau.currentText()
        
        filename, _ = QFileDialog.getSaveFileName(self, "Enregistrer le classement", 
                                                f"classement_{annee}_{niveau if niveau != 'Tous les niveaux' else 'all'}.pdf", 
                                                "PDF Files (*.pdf)")
        if not filename:
            return
        
        try:
            students_with_avg = self.db.get_all_students_with_average(annee=annee, niveau=(niveau if niveau != "Tous les niveaux" else None))
            students_with_avg = [s for s in students_with_avg if s[4] is not None]
            students_with_avg.sort(key=lambda x: x[4] if x[4] is not None else -1, reverse=True)
            
            if not students_with_avg:
                QMessageBox.warning(self, "Attention", "Aucun étudiant avec des notes pour l'export.")
                return
            
            with PdfPages(filename) as pdf:
                plt.figure(figsize=(12, 10))
                
                
                fig, ax = plt.subplots(figsize=(12, 10))
                ax.axis('tight')
                ax.axis('off')
                
                
                table_data = [["Rang", "N° Inscription", "Nom", "Niveau", "Année", "Moyenne"]]
                
                for rang, (n_insc, nom, niv, annee_etud, moyenne) in enumerate(students_with_avg, 1):
                    table_data.append([
                        str(rang),
                        n_insc,
                        nom,
                        niv,
                        str(annee_etud),
                        f"{moyenne:.2f}" if moyenne is not None else "N/A"
                    ])
                
                
                table = ax.table(cellText=table_data, loc='center', cellLoc='center')
                table.auto_set_font_size(False)
                table.set_fontsize(8)
                table.scale(1, 1.5)
                
                
                plt.title(f"Classement des Étudiants - Année {annee}\nNiveau: {niveau}", fontsize=16, fontweight='bold', pad=20)
                
                pdf.savefig(fig, bbox_inches='tight')
                plt.close()
            
            QMessageBox.information(self, "Succès", f"Classement exporté: {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors de l'export: {str(e)}")

def main():
    app = QApplication(sys.argv)
    
    
    app.setStyle('Fusion')
    
    
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(240, 240, 240))
    palette.setColor(QPalette.WindowText, QColor(0, 0, 0))
    app.setPalette(palette)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()