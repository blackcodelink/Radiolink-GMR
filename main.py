"""
Radiolink - DICOM Server Management Interface
Copyright (c) 2024 BlackCodeLink. All rights reserved.

This module implements the graphical user interface for managing the Radiolink DICOM server.
It provides functionality for server control, configuration management, and process monitoring.

Key features:
- Server start/stop/restart capabilities 
- Configuration management for AE Title, Port, and Technician settings
- Real-time process monitoring with auto-refresh
- Secure authentication for technician access
- Clean and intuitive navigation interface

Dependencies:
- flet: For building the GUI
- requests: For authentication API calls
- threading: For background tasks
- concurrent.futures: For server management
"""

import flet as ft
from db import get_config, update_config
from dicom_server import dicom_server
import threading
import concurrent.futures
from db import get_procs
import time
import requests


# Global state management
dicom_server_future = None  # Tracks the running server instance
task_lock = threading.Lock()  # Lock for thread-safe server operations
update_thread = None  # Background thread for auto-updating process list
config = {}  # Current server configuration


def start_dicom_server():
    """
    Starts the DICOM server in a background thread using ThreadPoolExecutor.
    Uses task_lock to ensure thread-safe server management.
    """
    global dicom_server_future

    with task_lock:
        # Cancel existing server if running
        if dicom_server_future is not None:
            dicom_server_future.cancel()

        # Start new server in background thread
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        dicom_server_future = executor.submit(dicom_server)


def restart_dicom_server(page):
    """
    Restarts the DICOM server with current configuration.
    
    Args:
        page: The current Flet page instance for UI updates
    """
    print("Restarting DICOM server...")
    start_dicom_server()
    
    # Show success message
    page.snack_bar = ft.SnackBar(
        content=ft.Text("DICOM server restarted successfully"),
        bgcolor=ft.colors.GREEN_700
    )
    page.snack_bar.open = True
    page.update()

# Initialize global config
config = get_config()


# Start initial DICOM server with current config values
start_dicom_server()


def save_settings(e, page):
    """
    Validates and saves server configuration settings.
    
    Args:
        e: Event object
        page: Current Flet page instance
    """
    settings_column = page.controls[0].controls[2].controls[0]
    ae_title = settings_column.controls[1].value
    port = int(settings_column.controls[2].value)  # Convert port to integer
    technician_email = settings_column.controls[3].value
    
    # Validate port number
    if not (1024 <= port <= 65535):
        page.snack_bar = ft.SnackBar(
            content=ft.Text("Port must be between 1024 and 65535"),
            bgcolor=ft.colors.RED_700
        )
        page.snack_bar.open = True
        page.update()
        return
        
    # Validate AE title
    if not ae_title or len(ae_title) > 16:
        page.snack_bar = ft.SnackBar(
            content=ft.Text("AE Title must be between 1 and 16 characters"),
            bgcolor=ft.colors.RED_700
        )
        page.snack_bar.open = True
        page.update()
        return
    
    # Show snackbar before restart
    page.snack_bar = ft.SnackBar(
        content=ft.Text("Settings saved successfully. Server restarting..."),
        bgcolor=ft.colors.GREEN_700
    )
    page.snack_bar.open = True
    page.update()
    
    # Update global config
    global config
    config["AE_TITLE"] = ae_title
    config["PORT"] = port
    config["TECHNICIAN_EMAIL"] = technician_email
    
    # Update config file and restart DICOM server with new settings
    update_config(ae_title, port, technician_email)
    restart_dicom_server(page)
    
    # Reload the application with fresh config
    config = get_config()
    page.clean()
    main(page)


def update_data_table(data_table, page):
    """
    Updates the process monitoring data table with fresh data.
    
    Args:
        data_table: The DataTable widget to update
        page: Current Flet page instance
    """
    data_table.rows = [
        ft.DataRow(
            cells=[
                ft.DataCell(ft.Text(str(proc[0]))),
                ft.DataCell(ft.Text(str(proc[1]))),
                ft.DataCell(ft.Text(str(proc[2]))),
                ft.DataCell(ft.Text(str(proc[3]))),
                ft.DataCell(ft.Text(str(proc[4]))),  # Status
                ft.DataCell(ft.Text(f"{proc[5]}%")),  # Upload percentage
            ],
        ) for proc in get_procs()
    ]
    page.update()


def start_auto_update(data_table, page):
    """
    Starts a background thread for automatic data table updates.
    
    Args:
        data_table: The DataTable widget to auto-update
        page: Current Flet page instance
    """
    global update_thread
    def update_loop():
        while True:
            update_data_table(data_table, page)
            time.sleep(1)
    
    update_thread = threading.Thread(target=update_loop, daemon=True)
    update_thread.start()


def login(email, password, page):
    """
    Authenticates technician credentials against the remote API.
    
    Args:
        email: Technician email
        password: Technician password
        page: Current Flet page instance
        
    Returns:
        bool: True if login successful, False if invalid credentials, None if network error
    """
    try:
        response = requests.post(f"https://admin.gmrnetwork.in/api/v1/users/login/", 
                               json={"email": email, "password": password})
        status = response.status_code
        if status == 200:
            # Update global config and restart server with new email
            global config
            config["TECHNICIAN_EMAIL"] = email
            update_config(config["AE_TITLE"], config["PORT"], email)
            restart_dicom_server(page)
            return True
        else:
            return False
    except requests.exceptions.RequestException as e:
        print(f"Error logging in: {e}")
        return None


def handle_close(e, page):
    """Closes the login dialog."""
    page.dialog.open = False
    page.update()


def handle_login(e, page, email_field, password_field, login_button, progress_ring, cancel_button):
    """
    Handles the login button click event.
    
    Args:
        e: Event object
        page: Current Flet page instance
        email_field: Email input field
        password_field: Password input field
        login_button: Login button widget
        progress_ring: Loading indicator widget
        cancel_button: Cancel button widget
    """
    email = email_field.value
    password = password_field.value
    
    # Show loading animation and hide login and cancel buttons
    progress_ring.visible = True
    login_button.visible = False
    cancel_button.visible = False
    page.update()
    
    login_result = login(email, password, page)
    
    # Hide loading animation and show login and cancel buttons
    progress_ring.visible = False
    login_button.visible = True
    cancel_button.visible = True
    
    if login_result is True:
        # Close dialog first
        page.dialog.open = False
        
        page.snack_bar = ft.SnackBar(
            content=ft.Text("Login successful!"),
            bgcolor=ft.colors.GREEN_700
        )
        page.snack_bar.open = True
        page.update()
        
        # Reload the application with fresh config
        global config
        config = get_config()
        page.clean()
        main(page)
    elif login_result is False:
        page.snack_bar = ft.SnackBar(
            content=ft.Text("Invalid email or password"),
            bgcolor=ft.colors.RED_700
        )
        page.snack_bar.open = True
        page.update()
    else:
        page.snack_bar = ft.SnackBar(
            content=ft.Text("Network error occurred. Please try again."),
            bgcolor=ft.colors.RED_700
        )
        page.snack_bar.open = True
        page.update()


def open_login_window(e, page):
    """
    Opens the login dialog window.
    
    Args:
        e: Event object
        page: Current Flet page instance
    """
    email_field = ft.TextField(label="Email", width=350)
    password_field = ft.TextField(label="Password", password=True, width=350)
    
    # Create progress ring for loading animation
    progress_ring = ft.ProgressRing(visible=False, width=16, height=16)
    
    # Create login button with loading state
    login_button = ft.TextButton(
        "Login",
        style=ft.ButtonStyle(
            padding=ft.padding.all(20),
            bgcolor=ft.colors.BLUE_200,
            color=ft.colors.GREY_900,
            shape=ft.RoundedRectangleBorder(radius=10),
        ),
    )

    # Create cancel button
    cancel_button = ft.TextButton(
        "Cancel", 
        style=ft.ButtonStyle(
            padding=ft.padding.all(20),
            bgcolor=ft.colors.GREY_300,
            color=ft.colors.GREY_900,
            shape=ft.RoundedRectangleBorder(radius=10),
        ),
    )
    
    # Update button click handlers
    login_button.on_click = lambda e: handle_login(e, page, email_field, password_field, login_button, progress_ring, cancel_button)
    cancel_button.on_click = lambda e: handle_close(e, page)
    
    login_window = ft.AlertDialog(
        modal=True,
        title=ft.Text("Login"),
        content=ft.Container(
            content=ft.Column(
                controls=[
                    email_field,
                    password_field,
                ],
                spacing=10,
                width=350,
            ),
            width=350,
            height=100
        ),
        actions=[
            ft.Row(
                controls=[
                    cancel_button,
                    ft.Row(
                        controls=[
                            login_button,
                            progress_ring,
                        ],
                        spacing=10,
                    ),
                ],
                alignment=ft.MainAxisAlignment.END,
                spacing=10,
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    page.dialog = login_window
    page.dialog.open = True
    page.update()


def main(page: ft.Page):
    """
    Main application entry point. Sets up the UI layout and navigation.
    
    Args:
        page: The root Flet page instance
    """
    page.title = "Radiolink"
    page.window.width = 900
    page.window.height = 800

    def handle_navigation_change(e):
        """Handles navigation rail selection changes."""
        content_column.controls.clear()
        selected_index = e.control.selected_index
        
        if selected_index == 0:  # Processes
            data_table = ft.DataTable(
                columns=[
                    ft.DataColumn(ft.Text("ID")),
                    ft.DataColumn(ft.Text("Patient ID")),
                    ft.DataColumn(ft.Text("Patient Name")),
                    ft.DataColumn(ft.Text("Images")),
                    ft.DataColumn(ft.Text("Status")),
                    ft.DataColumn(ft.Text("Upload %")),
                ],
                rows=[
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(str(proc[0]))),
                            ft.DataCell(ft.Text(str(proc[1]))),
                            ft.DataCell(ft.Text(str(proc[2]))),
                            ft.DataCell(ft.Text(str(proc[3]))),
                            ft.DataCell(ft.Text(str(proc[4]))),  # Status
                            ft.DataCell(ft.Text(f"{proc[5]}%")),  # Upload percentage
                        ],
                    ) for proc in get_procs()
                ],
                width=900,
                heading_row_color=ft.colors.BLUE_50,
            )
            
            # Start auto-update immediately
            start_auto_update(data_table, page)
            
            content_column.controls.append(
                ft.Column([
                    ft.Text("Processes View", size=20, weight=ft.FontWeight.BOLD),
                    data_table
                ])
            )
        else:  # Settings
            content_column.controls.append(
                ft.Column([
                    ft.Text("Settings", size=20, weight=ft.FontWeight.BOLD),
                    ft.TextField(label="AE Title", value=config.get("AE_TITLE")),
                    ft.TextField(label="Port", value=config.get("PORT")),
                    ft.TextField(label="Technician Email", value=config.get("TECHNICIAN_EMAIL"), disabled=True),
                    ft.ElevatedButton(
                        text="Save Settings",
                        style=ft.ButtonStyle(
                            color=ft.colors.WHITE,
                            bgcolor=ft.colors.BLUE_500,
                            padding=ft.padding.only(left=20, right=20)
                        ),
                        on_click=lambda e: save_settings(e, page)
                    ),

                    ft.Container(
                        content=ft.Column([
                            ft.Text(
                                "Authentication",
                                size=18,
                                weight=ft.FontWeight.BOLD,
                                color=ft.colors.BLUE_GREY_800
                            ),
                            ft.Text(
                                "Login to manage technician settings",
                                size=14,
                                color=ft.colors.BLUE_GREY_600
                            ),
                            ft.ElevatedButton(
                                text="Login",
                                on_click=lambda e: open_login_window(e, page),
                                style=ft.ButtonStyle(
                                    color=ft.colors.WHITE,
                                    bgcolor=ft.colors.BLUE_500,
                                    padding=ft.padding.symmetric(horizontal=30, vertical=15),
                                    shape=ft.RoundedRectangleBorder(radius=8),
                                    elevation=2,
                                    animation_duration=200,
                                ),
                            )
                        ],
                        spacing=8,
                        ),
                        margin=ft.margin.only(top=30),
                        padding=ft.padding.all(20),
                        border_radius=10,
                        bgcolor=ft.colors.BLUE_50,
                    )
                ])
            )
        page.update()

    rail = ft.NavigationRail(
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        min_width=100,
        min_extended_width=400,
        group_alignment=-0.9,
        destinations=[
            ft.NavigationRailDestination(
                icon=ft.icons.VIEW_LIST_OUTLINED,
                selected_icon=ft.icons.VIEW_LIST,
                label="Processes"
            ),
            ft.NavigationRailDestination(
                icon=ft.icons.SETTINGS_OUTLINED,
                selected_icon=ft.icons.SETTINGS,
                label="Settings"
            ),
        ],
        on_change=handle_navigation_change,
    )

    content_column = ft.Column(
        [
            ft.Column([
                ft.Text("Processes View", size=20, weight=ft.FontWeight.BOLD),
                ft.DataTable(
                    columns=[
                        ft.DataColumn(ft.Text("ID")),
                        ft.DataColumn(ft.Text("Patient ID")),
                        ft.DataColumn(ft.Text("Patient Name")),
                        ft.DataColumn(ft.Text("Images")),
                        ft.DataColumn(ft.Text("Status")),
                        ft.DataColumn(ft.Text("Upload %")),
                    ],
                    rows=[
                        ft.DataRow(
                            cells=[
                                ft.DataCell(ft.Text(str(proc[0]))),
                                ft.DataCell(ft.Text(str(proc[1]))),
                                ft.DataCell(ft.Text(str(proc[2]))),
                                ft.DataCell(ft.Text(str(proc[3]))),
                                ft.DataCell(ft.Text(str(proc[4]))),  # Status
                                ft.DataCell(ft.Text(f"{proc[5]}%")),  # Upload percentage
                            ],
                        ) for proc in get_procs()
                    ],
                    width=900,
                    heading_row_color=ft.colors.BLUE_50,
                ),
            ])
        ],
        alignment=ft.MainAxisAlignment.START,
        expand=True,
    )

    # Start auto-update immediately when app launches
    data_table = content_column.controls[0].controls[1]
    start_auto_update(data_table, page)

    page.add(
        ft.Row(
            [
                rail,
                ft.VerticalDivider(width=1),
                content_column,
            ],
            expand=True,
        )
    )

ft.app(target=main)
