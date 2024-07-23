import sys
from PyQt5.QtWidgets import QApplication, QPlainTextEdit, QProgressBar, QHBoxLayout, QComboBox, QWidget, QVBoxLayout, QLabel, QPushButton, QLineEdit, QFileDialog, QMessageBox
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QFont
import gitlab
import os

class GitLabIssueGrabber(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Gitlab Issue Grabber')
        self.setGeometry(300, 300, 500, 500)

        layout = QVBoxLayout()

        # Colorful title
        title_label = QLabel('GitLab Grabber')
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setFont(QFont('Arial', 20, QFont.Bold))
        title_label.setStyleSheet("color: #4a86e8;")
        layout.addWidget(title_label)

        author_label = QLabel('Written by Gerald Jackson')
        author_label.setAlignment(Qt.AlignCenter)
        author_label.setFont(QFont('Arial', 8))
        author_label.setStyleSheet("color: #6aa84f;")
        layout.addWidget(author_label)

        # API Key input
        api_layout = QHBoxLayout()
        api_layout.addWidget(QLabel('API Key:'))
        self.api_key_input = QLineEdit()
        api_layout.addWidget(self.api_key_input)
        layout.addLayout(api_layout)

        # Subsystem dropdown
        subsystem_layout = QHBoxLayout()
        subsystem_layout.setAlignment(Qt.AlignCenter)
        subsystem_layout.addWidget(QLabel('Subsystem:'))
        self.subsystem_dropdown = QComboBox()
        self.subsystem_dropdown.addItems(['Cold Tree', 'Pump Cart', 'Tail Set', 'Controls', 'Integration', 'Electrical', 'Assembly', 'Magnetics'])
        subsystem_layout.addWidget(self.subsystem_dropdown)
        layout.addLayout(subsystem_layout)

        # Description keywords input
        keywords_layout = QHBoxLayout()
        keywords_layout.addWidget(QLabel('Description Keywords:\n(keyword1, keyword2,)\nLeave Blank to grab all'))
        self.keywords_input = QLineEdit()
        keywords_layout.addWidget(self.keywords_input)
        layout.addLayout(keywords_layout)

        # Output directory selection
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel('Output Directory:'))
        self.output_path = QLineEdit()
        output_layout.addWidget(self.output_path)
        self.browse_button = QPushButton('Browse')
        self.browse_button.clicked.connect(self.browse_directory)
        output_layout.addWidget(self.browse_button)
        layout.addLayout(output_layout)

        # Run button
        self.run_button = QPushButton('Run')
        self.run_button.clicked.connect(self.run_script)
        layout.addWidget(self.run_button)

        # Add progress bar
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setAlignment(Qt.AlignCenter)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Output text area
        self.output_text = QPlainTextEdit()
        self.output_text.setReadOnly(True)
        layout.addWidget(self.output_text)

        self.setLayout(layout)

        # Timer for fake progress
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_fake_progress)

    def browse_directory(self):
        dialog = QFileDialog()
        folder_path = dialog.getExistingDirectory(None, "Select Folder")
        self.output_path.setText(folder_path)

    def run_script(self):
        api_key = self.api_key_input.text()
        subsystem = self.subsystem_dropdown.currentText()
        keywords = self.keywords_input.text()
        output_dir = self.output_path.text()

        if not all([api_key, subsystem, output_dir]):
            QMessageBox.warning(self, "Input Error", "API Key, Subsystem, and Output Directory must be filled.")
            return

        self.thread = GitLabIssueGrabberThread(api_key, subsystem, keywords, output_dir)
        self.thread.update_signal.connect(self.update_output)
        self.thread.finished_signal.connect(self.script_finished)
        self.thread.start()

        self.run_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.timer.start(100)  # Update every 50ms

    def update_output(self, text):
        self.output_text.appendPlainText(text)

    def update_fake_progress(self):
        current_value = self.progress_bar.value()
        if current_value < 95:
            self.progress_bar.setValue(current_value + 1)

    def script_finished(self, message):
        self.run_button.setEnabled(True)
        self.timer.stop()
        self.progress_bar.setValue(100)
        QTimer.singleShot(500, lambda: self.progress_bar.setVisible(False))
        QMessageBox.information(self, "Script Finished", message)

class GitLabIssueGrabberThread(QThread):
    update_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(str)

    def __init__(self, api_key, subsystem_term, description_terms, output_dir):
        QThread.__init__(self)
        self.api_key = api_key
        self.subsystem_term = subsystem_term
        self.description_terms = description_terms
        self.output_dir = output_dir

    def run(self):
        try:
            gl = gitlab.Gitlab(url='https://acstgitlab.honeywell.com/', private_token=self.api_key)
            gl.auth()

            group_id = 725
            description_terms = [term.strip() for term in self.description_terms.split(',')] if self.description_terms else []

            if description_terms:
                output_file_name = f"{self.subsystem_term.replace(' ', '_')}_{description_terms[0].replace(' ', '_')}.txt"
            else:
                output_file_name = f"{self.subsystem_term.replace(' ', '_')}_all_issues.txt"
            output_file_path = os.path.join(self.output_dir, output_file_name)

            def issue_matches(issue, subsystem_term, description_terms):
                if issue.state != 'opened':
                    return False
                if any(subsystem_term.lower() in label.lower() for label in issue.labels):
                    if not description_terms:
                        return True
                    if issue.description:
                        description_lower = issue.description.lower()
                        return any(term.lower() in description_lower for term in description_terms)
                return False

            with open(output_file_path, 'w', encoding='utf-8') as f:
                group = gl.groups.get(group_id)
                issues = group.issues.list(all=True)

                f.write(f"Gitlab Data Grabber - Written by: Gerald Jackson Date: 7/15/2024 V1.2\n\n")
                f.write(f"Issues containing '{self.subsystem_term}' in labels")
                if description_terms:
                    f.write(f" and '{' or '.join(description_terms)}' in description")
                f.write(f" for Group: {group.name} (ID: {group.id})\n\n")

                matching_issues = []
                total_issues = len(issues)
            
                self.update_signal.emit(f"Searching through {total_issues} issues...")

                for index, issue in enumerate(issues, 1):
                    if issue_matches(issue, self.subsystem_term, description_terms):
                        matching_issues.append(issue)
                        self.update_signal.emit(f"Found matching issue: #{issue.iid} - {issue.title}")
                
                    if index % 20 == 0 or index == total_issues:  # Update every 20 issues or at the end
                        self.update_signal.emit(f"Processed {index}/{total_issues} issues...")

                total_matching_issues = len(matching_issues)

                f.write(f"Total Matching Issues: {total_matching_issues}\n\n")

                if not matching_issues:
                    f.write(f"No issues found matching the criteria\n")
                    self.update_signal.emit("No issues found matching the criteria")
                else:
                    for issue in matching_issues:
                        issue_info = f"Title: {issue.title}\n"
                        issue_info += f"ID: {issue.iid}\n"
                        issue_info += f"State: {issue.state}\n"
                        issue_info += f"Created at: {issue.created_at}\n"
                        issue_info += f"URL: {issue.web_url}\n"
                        issue_info += f"Labels: {', '.join(issue.labels)}\n"
                        if issue.description:
                            issue_info += f"Description: {issue.description}\n"
                        else:
                            issue_info += "Description: No description available\n"
                        issue_info += "-" * 50 + "\n"
                        f.write(issue_info)

                self.update_signal.emit(f"Matching issues have been written to {output_file_path}")
                self.update_signal.emit(f"Total matching open issues: {total_matching_issues}")
            
            self.finished_signal.emit("Issues have been successfully grabbed and saved.")
        except Exception as e:
            self.finished_signal.emit(f"An error occurred: {str(e)}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = GitLabIssueGrabber()
    ex.show()
    sys.exit(app.exec_())