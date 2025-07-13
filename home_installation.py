import cv2
import pygame
import time
import os
import subprocess
import signal
import threading

# Constants
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
RECORD_SECONDS = 30
PREP_SECONDS = 5
FONT_SIZE = 36
FONT_COLOR = (255, 255, 255)
BACKGROUND_COLOR = (0, 0, 0)
VIDEO_FOLDER = "recordings"
TEMP_AUDIO_PLAYBACK = "temp_audio_playback.wav"

# Setup
os.makedirs(VIDEO_FOLDER, exist_ok=True)
pygame.init()
pygame.mixer.init()
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("Home Installation")
font = pygame.font.SysFont("Arial", FONT_SIZE)
clock = pygame.time.Clock()

def display_message(message, duration, countdown=False):
    """Display a message on screen with optional countdown"""
    end_time = time.time() + duration
    while time.time() < end_time:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return True
        
        screen.fill(BACKGROUND_COLOR)
        text = font.render(message, True, FONT_COLOR)
        rect = text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 20))
        screen.blit(text, rect)

        if countdown:
            remaining = int(end_time - time.time()) + 1  # +1 to show countdown properly
            if remaining > 0:
                timer_text = font.render(str(remaining), True, FONT_COLOR)
                timer_rect = timer_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 40))
                screen.blit(timer_text, timer_rect)

        pygame.display.flip()
        clock.tick(30)
    return False

def test_camera_and_audio():
    """Test if camera and audio devices are available"""
    print("Testing camera...")
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: Cannot access camera!")
        return False
    cap.release()
    print("Camera OK")
    
    # Test ffmpeg availability
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        if result.returncode != 0:
            print("ERROR: ffmpeg not found!")
            return False
        print("ffmpeg OK")
    except FileNotFoundError:
        print("ERROR: ffmpeg not installed!")
        return False
    
    # List available devices (macOS)
    try:
        result = subprocess.run(["ffmpeg", "-f", "avfoundation", "-list_devices", "true", "-i", ""], 
                              capture_output=True, text=True)
        print("Available devices:")
        print(result.stderr)  # ffmpeg outputs device list to stderr
    except Exception as e:
        print(f"Could not list devices: {e}")
    
    return True

def record_video_with_audio():
    """Record video with audio using ffmpeg and show preview with pygame/opencv"""
    timestamp = int(time.time())
    output_path = os.path.join(VIDEO_FOLDER, f"{timestamp}.mp4")
    
    print(f"Starting recording to: {output_path}")
    
    # Improved ffmpeg command for better audio sync
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-f", "avfoundation",
        "-framerate", "30",
        "-video_size", "1280x720",
        "-i", "0:1",  # Video device 0, audio device 1 (MacBook Pro Microphone)
        "-t", str(RECORD_SECONDS),
        "-c:v", "libx264",
        "-preset", "fast",      # Better quality than ultrafast
        "-crf", "23",           # Good quality setting
        "-c:a", "aac",
        "-ar", "44100",         # Standard audio sample rate
        "-ac", "2",             # Stereo audio
        "-async", "1",          # Audio sync compensation
        "-vsync", "cfr",        # Constant frame rate for sync
        "-avoid_negative_ts", "make_zero",  # Handle timestamp issues
        output_path
    ]
    
    print("FFmpeg command:", " ".join(ffmpeg_cmd))
    
    # Start ffmpeg recording
    try:
        process = subprocess.Popen(ffmpeg_cmd, 
                                 stdout=subprocess.PIPE, 
                                 stderr=subprocess.PIPE)
    except Exception as e:
        print(f"Failed to start ffmpeg: {e}")
        return

    # Start preview using OpenCV
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: Cannot open camera for preview")
        process.terminate()
        return
    
    start_time = time.time()
    recording_stopped = False

    while True:
        elapsed = time.time() - start_time
        if elapsed > RECORD_SECONDS:
            break

        ret, frame = cap.read()
        if not ret:
            print("WARNING: Failed to read frame from camera")
            break

        # Convert and display frame
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_rgb = cv2.resize(frame_rgb, (1280, 720))
        surf = pygame.surfarray.make_surface(frame_rgb.swapaxes(0, 1))
        screen.blit(surf, (0, 0))

        # Show recording timer
        remaining = int(RECORD_SECONDS - elapsed)
        timer_text = font.render(f"Recording... {remaining}s", True, (255, 0, 0))
        screen.blit(timer_text, (20, 20))
        
        # Show recording indicator
        record_indicator = font.render("● REC", True, (255, 0, 0))
        screen.blit(record_indicator, (20, 60))
        
        pygame.display.flip()

        # Handle events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                recording_stopped = True
                break
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                print("Recording stopped by user")
                recording_stopped = True
                break
        
        if recording_stopped:
            break

        clock.tick(30)

    # Clean up
    cap.release()
    
    # Stop ffmpeg process
    if process.poll() is None:  # Process is still running
        print("Stopping ffmpeg...")
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print("Force killing ffmpeg...")
            process.kill()
            process.wait()
    
    # Check if recording was successful
    stdout, stderr = process.communicate()
    if process.returncode != 0:
        print(f"FFmpeg error (return code: {process.returncode}):")
        print(f"STDOUT: {stdout.decode()}")
        print(f"STDERR: {stderr.decode()}")
    else:
        print(f"Recording completed successfully: {output_path}")
        if os.path.exists(output_path):
            size = os.path.getsize(output_path)
            print(f"File size: {size} bytes")
        else:
            print("WARNING: Output file was not created!")

def play_idle_loop():
    """Play recorded videos in a loop during idle state"""
    while True:
        video_files = sorted([f for f in os.listdir(VIDEO_FOLDER) if f.endswith(".mp4")])
        
        if not video_files:
            # No videos available - show waiting message
            screen.fill(BACKGROUND_COLOR)
            text = font.render("Press SPACE to record your story about home", True, FONT_COLOR)
            rect = text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2))
            screen.blit(text, rect)
            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return True
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                    return False
            clock.tick(30)
            continue

        # Play each video file
        for video_file in video_files:
            filepath = os.path.join(VIDEO_FOLDER, video_file)
            print(f"Playing: {filepath}")
            
            cap = cv2.VideoCapture(filepath)
            if not cap.isOpened():
                print(f"Could not open video: {filepath}")
                continue

            # Get video properties
            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0:
                fps = 30  # Default fallback
            frame_delay = 1.0 / fps

            # Extract and play audio
            audio_thread = None
            try:
                # Extract audio to WAV for better pygame compatibility
                subprocess.run([
                    "ffmpeg", "-y", "-i", filepath, 
                    "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
                    TEMP_AUDIO_PLAYBACK
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

                if os.path.exists(TEMP_AUDIO_PLAYBACK):
                    pygame.mixer.music.load(TEMP_AUDIO_PLAYBACK)
                    pygame.mixer.music.play()
            except Exception as e:
                print(f"Audio extraction/playback error: {e}")

            # Play video frames
            last_frame_time = time.time()
            
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break

                # Frame timing
                current_time = time.time()
                if current_time - last_frame_time < frame_delay:
                    time.sleep(frame_delay - (current_time - last_frame_time))
                last_frame_time = time.time()

                # Display frame
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame_rgb = cv2.resize(frame_rgb, (WINDOW_WIDTH, WINDOW_HEIGHT))
                surf = pygame.surfarray.make_surface(frame_rgb.swapaxes(0, 1))
                screen.blit(surf, (0, 0))
                
                # Show playback indicator
                play_text = font.render("Playing recordings - Press SPACE to record new", True, (255, 255, 255))
                screen.blit(play_text, (20, WINDOW_HEIGHT - 40))
                
                pygame.display.flip()

                # Handle events
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        cap.release()
                        pygame.mixer.music.stop()
                        if os.path.exists(TEMP_AUDIO_PLAYBACK):
                            os.remove(TEMP_AUDIO_PLAYBACK)
                        return True
                    elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                        cap.release()
                        pygame.mixer.music.stop()
                        if os.path.exists(TEMP_AUDIO_PLAYBACK):
                            os.remove(TEMP_AUDIO_PLAYBACK)
                        return False

            cap.release()
            pygame.mixer.music.stop()
            
            # Clean up audio file
            if os.path.exists(TEMP_AUDIO_PLAYBACK):
                os.remove(TEMP_AUDIO_PLAYBACK)

# Main execution
def main():
    print("=== Home Installation Starting ===")
    
    # Test system capabilities
    if not test_camera_and_audio():
        print("System test failed. Please check camera and ffmpeg installation.")
        pygame.quit()
        return
    
    print("System test passed. Starting main loop...")
    
    running = True
    while running:
        # Idle state - play existing recordings
        if play_idle_loop():
            break
        
        # Preparation phase
        if display_message("What does home mean to you?", PREP_SECONDS, countdown=True):
            break
        
        # Recording phase
        record_video_with_audio()
        
        # Thank you message
        if display_message("Thank you for sharing your story!", 3):
            break

    pygame.quit()
    print("=== Installation Ended ===")

if __name__ == "__main__":
    main()