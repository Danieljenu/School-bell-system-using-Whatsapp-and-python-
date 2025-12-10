# JOTHI: Smart School Bell & Assembly Automation System
(Without WhatsApp Integration or GUI)

JOTHI is an advanced, menu-driven Python application designed to automate and modernize the daily operations of a school’s bell system and assembly procedures. The project was built to replace the traditional, manually-operated bell program and create a more structured, reliable, and user-friendly system.

The entire system runs in the Python terminal and uses PyGame for audio playback. It includes multiple modules such as Bell Scheduling, Assembly Control, Announcements, and Settings — all operating without the need for external databases or graphical interfaces.

🔔 1. Bell Mode – Automated School Bell Scheduler

Bell Mode allows the school to schedule and automatically ring bells throughout the day.

Features:

Create custom bell schedules

Edit, rename, or delete schedules

View and use saved schedules

Set Today’s Bell Times for one-day events

Automated ringing using real-time time checks

Prevents ringing when Assembly Mode is active

Uses PyGame to play bell.mp3 at the scheduled time

Fully menu-driven and easy to navigate

This module ensures consistent bell timings and eliminates human error in daily operations.

🎤 2. Assembly Mode – Day-Based Audio Management

Assembly Mode is designed to manage school assembly functions with full control over different days’ requirements.

Features:

Detects the current day (Monday–Friday)

Automatically selects the correct:

Prayer audio (English, Hindi, or Malayalam)

Birthday song audio

Provides manual buttons for:

Prayer

Birthday song

National anthem

Extra Audio 1 & 2

Assembly Bell (5 seconds)

Assembly playback overrides Bell Mode to avoid interference during morning functions.

📢 3. Announcement Mode (Placeholder)

A placeholder module reserved for future expansion.
It will manage general announcements or audio playback beyond assembly.

⚙️ 4. Settings – Full Customization

Users can customize almost every audio element in the system.

Changeable Settings:

National Anthem audio file

Assembly Bell audio file

Extra Audio 1 & 2

Per-day:

Prayer audio

Birthday audio

Day label (e.g., “English Day”)

Settings allow complete flexibility for different schools or events.

🧠 5. Internal System Logic

Uses Python dictionaries and lists for data storage

Uses datetime for real-time checking

Protects modes from overlapping (Assembly prevents Bell)

Includes clean error handling and input validation

Easily extendable with new features

Runs fully offline

🎯 6. Purpose of the Project

The project was created to:

Provide a structured, automated, and reliable school bell system

Replace outdated shell programs with many limitations

Make the bell and assembly operations easier for staff

Bring day-specific configuration without requiring technical knowledge

Run using simple menu navigation (no need for GUI)

It was developed with the intention of improving school workflow and removing the burden of manual bell management.

💖 Dedication

This project is lovingly dedicated to Mrs. Jyothi Suresh, Vice Principal of Sree Gokulam Public School, whose encouragement and inspiration helped spark the creation of this system.

🧑‍💻 Developer

Created by Daniel, Class 12 Computer Science student, as part of a passion-driven school automation initiative.QL
