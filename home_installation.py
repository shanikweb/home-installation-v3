#!/usr/bin/env python3
"""
Home Installation - With Audio Playback
"""

import cv2
import pygame
import time
import os
import subprocess
import tempfile
from datetime import datetime
from enum import Enum
import numpy as np
import threading

class State(Enum):
    IDLE = "idle"
    PROMPT = "prompt" 
    RECORDING = "recording"
    THANKYOU = "thankyou"

class HomeInstallation:
    def __init__(self):
        # Configuration
        self.RECORDING_TIME = 30
        self.PROMPT_TIME = 3
        self.THANKYOU_TIME = 2
        
        # Directories
        self.recordings_dir = "recordings"
        self.videos_dir = "videos"
        os.makedirs(self.recordings_dir, exist_ok=True)
        os.makedirs(self.videos_dir, exist_ok=True)
        
        # State management
        self.current_state = State.IDLE
        self.state_start_time = time.time()
        self.can_finish_early = False
        
        # Camera setup
        self.camera = None
        self.recording_process = None
        self.current_recording_path = None
        
        # Playback setup
        self.recorded_videos = []
        self.current_playback_index = 0
        self.current_playback_video = None
        self.playback_cap = None
        self.audio_process = None
        self.video_start_time = None
        self.video_fps = 30
        self.switching_video = False
        
        # Pygame setup
        pygame.init()
        self.screen_width = 1280
        self.screen_height = 720
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        pygame.display.set_caption("Home Installation")
        
        # Font and colors
        self.font_large = pygame.font.Font(None, 48)
        self.font_medium = pygame.font.Font(None, 36)
        self.font_small = pygame.font.Font(None, 24)
        self.WHITE = (255, 255, 255)
        self.BLACK = (0, 0, 0)
        self.RED = (255, 0, 0)
        self.GREEN = (0, 255, 0)
        
        # Audio device preferences
        self.preferred_audio_input = None  # Will be detected automatically
        self.preferred_audio_output = None  # Use system default
        self.audio_input_device_id = 0  # Default audio input device
        self.video_input_device_id = 0  # Default video input device
        
        # Custom video playback
        self.prompt_video_cap = None
        self.timer_video_cap = None  
        self.thankyou_video_cap = None
        self.custom_video_start_time = None
        
        # Custom video playback
        self.prompt_video_cap = None
        self.timer_video_cap = None  
        self.thankyou_video_cap = None
        self.custom_video_start_time = None
        
        # Status info
        self.camera_status = "Not initialized"
        self.recording_status = "Ready"
        self.camera_error = None
        
        print("Installation initialized!")
        self.scan_recorded_videos()
        self.test_audio_capabilities()
        self.detect_best_devices()
        self.check_custom_videos()
        self.test_camera_availability()
    
    def test_camera_availability(self):
        """Test if camera is available and get info"""
        print("\n=== CAMERA DEBUG ===")
        
        # Test different camera indices
        for i in range(3):  # Test cameras 0-2
            print(f"Testing camera index {i}...")
            test_cap = cv2.VideoCapture(i)
            if test_cap.isOpened():
                ret, frame = test_cap.read()
                if ret:
                    h, w = frame.shape[:2]
                    print(f"  ✅ Camera {i} works! Resolution: {w}x{h}")
                else:
                    print(f"  ❌ Camera {i} opened but can't read frames")
                test_cap.release()
            else:
                print(f"  ❌ Camera {i} failed to open")
        
        print("===================\n")
    
    def test_audio_capabilities(self):
        """Test audio playback and recording capabilities"""
        print("\n=== AUDIO DEVICE DEBUG ===")
        
        # Test ffplay
        try:
            result = subprocess.run(['ffplay', '-version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                print("✅ ffplay is available")
            else:
                print("❌ ffplay not working")
        except:
            print("❌ ffplay not found")
        
        # List available audio devices
        print("\n--- Available Audio Devices ---")
        try:
            # List AVFoundation devices
            result = subprocess.run(['ffmpeg', '-f', 'avfoundation', '-list_devices', 'true', '-i', '""'], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.stderr:
                lines = result.stderr.split('\n')
                in_audio_section = False
                in_video_section = False
                
                for line in lines:
                    if '[AVFoundation indev' in line:
                        if 'audio devices:' in line:
                            print("🎤 Audio Input Devices:")
                            in_audio_section = True
                            in_video_section = False
                        elif 'video devices:' in line:
                            print("📹 Video Input Devices:")
                            in_video_section = True
                            in_audio_section = False
                        elif in_audio_section and '] [' in line:
                            device_info = line.split('] ')[-1] if '] ' in line else line
                            print(f"   {device_info}")
                        elif in_video_section and '] [' in line:
                            device_info = line.split('] ')[-1] if '] ' in line else line
                            print(f"   {device_info}")
                        
        except Exception as e:
            print(f"❌ Could not list devices: {e}")
        
        # Check system volume
        try:
            result = subprocess.run(['osascript', '-e', 'output volume of (get volume settings)'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                volume = result.stdout.strip()
                print(f"\n📊 System volume: {volume}%")
                if int(volume) == 0:
                    print("⚠️  System volume is muted!")
        except:
            print("❓ Could not check system volume")
        
        print("===============================\n")
    
    def detect_best_devices(self):
        """Detect the best audio/video devices for the installation"""
        print("\n=== DEVICE SELECTION ===")
        
        try:
            # Get device list
            result = subprocess.run(['ffmpeg', '-f', 'avfoundation', '-list_devices', 'true', '-i', '""'], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.stderr:
                lines = result.stderr.split('\n')
                audio_devices = []
                video_devices = []
                current_section = None
                
                for line in lines:
                    if 'audio devices:' in line:
                        current_section = 'audio'
                    elif 'video devices:' in line:
                        current_section = 'video'
                    elif current_section and '] [' in line and 'AVFoundation' in line:
                        # Extract device ID and name
                        parts = line.split('] ')
                        if len(parts) >= 2:
                            device_info = parts[-1]
                            # Try to extract device ID (usually in brackets)
                            id_match = line.split('[')
                            if len(id_match) >= 2:
                                device_id = id_match[1].split(']')[0]
                                if device_id.isdigit():
                                    if current_section == 'audio':
                                        audio_devices.append((int(device_id), device_info))
                                    elif current_section == 'video':
                                        video_devices.append((int(device_id), device_info))
                
                # Select best devices
                print("🎤 Audio Input Selection:")
                usb_audio = None
                built_in_audio = None
                
                for device_id, device_name in audio_devices:
                    print(f"   [{device_id}] {device_name}")
                    if 'usb' in device_name.lower() or 'microphone' in device_name.lower():
                        usb_audio = device_id
                        print(f"      ✅ USB/External microphone detected!")
                    elif 'built-in' in device_name.lower() or 'internal' in device_name.lower():
                        built_in_audio = device_id
                
                # Prefer USB microphone over built-in
                if usb_audio is not None:
                    self.audio_input_device_id = usb_audio
                    print(f"🎤 Selected USB microphone (device {usb_audio})")
                elif built_in_audio is not None:
                    self.audio_input_device_id = built_in_audio
                    print(f"🎤 Selected built-in microphone (device {built_in_audio})")
                else:
                    self.audio_input_device_id = 0
                    print(f"🎤 Using default audio input (device 0)")
                
                # Select video device
                print("\n📹 Video Input Selection:")
                for device_id, device_name in video_devices:
                    print(f"   [{device_id}] {device_name}")
                    if 'built-in' in device_name.lower() or 'facetime' in device_name.lower():
                        self.video_input_device_id = device_id
                        print(f"      ✅ Built-in camera detected!")
                
                print(f"📹 Selected camera (device {self.video_input_device_id})")
                
        except Exception as e:
            print(f"❌ Device detection failed: {e}")
            print("🔧 Using default devices (0:0)")
            
        print("========================\n")
    
    def check_custom_videos(self):
        """Check for custom animation videos"""
        print("\n=== CUSTOM VIDEOS ===")
        
        video_files = {
            'prompt.mp4': 'Question animation',
            'timer.mp4': 'Recording timer', 
            'thankyou.mp4': 'Thank you animation'
        }
        
        for filename, description in video_files.items():
            filepath = os.path.join(self.videos_dir, filename)
            if os.path.exists(filepath):
                print(f"✅ {description}: {filename}")
            else:
                print(f"❌ Missing {description}: {filename}")
                print(f"   Create: {filepath}")
        
        print("=====================\n")
    
    def load_custom_video(self, video_name):
        """Load a custom video for playback"""
        video_path = os.path.join(self.videos_dir, f"{video_name}.mp4")
        
        if os.path.exists(video_path):
            cap = cv2.VideoCapture(video_path)
            if cap.isOpened():
                self.custom_video_start_time = time.time()
                return cap
            else:
                cap.release()
        return None
    
    def get_custom_video_frame(self, video_cap, fps=30):
        """Get current frame from custom video with timing"""
        if not video_cap or not self.custom_video_start_time:
            return None
        
        # Calculate which frame we should be at
        elapsed = time.time() - self.custom_video_start_time
        target_frame = int(elapsed * fps)
        
        # Set video to correct frame
        video_cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
        
        ret, frame = video_cap.read()
        if ret:
            # Resize to full window
            frame = cv2.resize(frame, (self.screen_width, self.screen_height))
            # Convert for pygame
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_rgb = np.transpose(frame_rgb, (1, 0, 2))
            return frame_rgb
        
        return None
    
    def scan_recorded_videos(self):
        """Scan for recorded videos and sort by newest first - only valid files"""
        try:
            video_files = []
            for file in os.listdir(self.recordings_dir):
                if file.endswith('.mp4'):
                    full_path = os.path.join(self.recordings_dir, file)
                    
                    # Check if file is valid and complete
                    if self.is_video_file_valid(full_path):
                        mtime = os.path.getmtime(full_path)
                        video_files.append((mtime, full_path))
                    else:
                        print(f"⚠️  Removing corrupted video: {file}")
                        try:
                            os.remove(full_path)
                        except:
                            pass
            
            # Sort by modification time (newest first)
            video_files.sort(reverse=True)
            self.recorded_videos = [path for _, path in video_files]
            
            print(f"Found {len(self.recorded_videos)} valid recorded videos")
            
        except Exception as e:
            print(f"Error scanning videos: {e}")
            self.recorded_videos = []
    
    def is_video_file_valid(self, video_path):
        """Check if video file is valid and playable"""
        try:
            # Check file size
            if os.path.getsize(video_path) < 1000:  # Less than 1KB
                return False
            
            # Try to open with OpenCV
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                cap.release()
                return False
            
            # Try to read first frame
            ret, frame = cap.read()
            cap.release()
            
            return ret and frame is not None
            
        except Exception as e:
            print(f"Video validation error for {video_path}: {e}")
            return False
    
    def setup_camera(self):
        """Initialize camera"""
        if self.camera is not None:
            return True
            
        print("Setting up camera...")
        
        # Try different camera indices
        for index in [0, 1, 2]:
            try:
                print(f"Trying camera {index}")
                self.camera = cv2.VideoCapture(index)
                
                if self.camera.isOpened():
                    # Test if we can actually read a frame
                    ret, frame = self.camera.read()
                    if ret:
                        print(f"✅ Camera {index} working!")
                        self.camera_status = f"Camera {index} active"
                        
                        # Set properties
                        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                        self.camera.set(cv2.CAP_PROP_FPS, 30)
                        
                        return True
                    else:
                        self.camera.release()
                        self.camera = None
                else:
                    if self.camera:
                        self.camera.release()
                        self.camera = None
                        
            except Exception as e:
                print(f"❌ Exception with camera {index}: {e}")
                if self.camera:
                    self.camera.release()
                    self.camera = None
        
        self.camera_status = "No camera found"
        print("❌ Failed to initialize camera")
        return False
    
    def start_recording(self):
        """Start recording with FFmpeg for audio+video"""
        print("Starting recording...")
        
        if not self.setup_camera():
            print("❌ Cannot start recording - no camera")
            self.recording_status = "No camera available"
            return False
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.current_recording_path = os.path.join(self.recordings_dir, f"response_{timestamp}.mp4")
            
            # Try FFmpeg first for audio recording
            if self.start_ffmpeg_recording():
                self.recording_status = f"Recording with audio: {os.path.basename(self.current_recording_path)}"
                self.can_finish_early = True
                print(f"✅ FFmpeg recording started: {self.current_recording_path}")
                return True
            else:
                print("⚠️  FFmpeg failed, recording without audio is not implemented in this version")
                self.recording_status = "FFmpeg required for recording"
                return False
                
        except Exception as e:
            print(f"❌ Recording setup failed: {e}")
            self.recording_status = f"Recording error: {str(e)}"
            return False
    
    def start_ffmpeg_recording(self):
        """Start ffmpeg recording process with smart device selection"""
        try:
            # Create FFmpeg command with selected devices
            cmd = [
                'ffmpeg',
                '-f', 'avfoundation',
                '-framerate', '30',
                '-video_size', '1280x720',
                '-i', f'{self.video_input_device_id}:{self.audio_input_device_id}',  # video:audio device IDs
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-preset', 'ultrafast',
                '-crf', '23',
                '-movflags', '+faststart',  # Move moov atom to beginning for better compatibility
                '-fflags', '+genpts',  # Generate presentation timestamps
                '-avoid_negative_ts', 'make_zero',  # Avoid negative timestamps
                '-max_muxing_queue_size', '1024',  # Increase muxing queue
                '-y',  # Overwrite output file
                self.current_recording_path
            ]
            
            print(f"🎬 Recording with devices - Video: {self.video_input_device_id}, Audio: {self.audio_input_device_id}")
            print(f"📋 FFmpeg command: {' '.join(cmd)}")
            
            self.recording_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=1,
                universal_newlines=True
            )
            
            # Give FFmpeg more time to start and check for immediate errors
            time.sleep(2)
            
            # Check if process is still running
            if self.recording_process.poll() is None:
                print("✅ FFmpeg process started successfully")
                return True
            else:
                # Process died, get error info
                stdout, stderr = self.recording_process.communicate()
                print(f"❌ FFmpeg failed immediately:")
                if stdout:
                    print(f"STDOUT: {stdout}")
                if stderr:
                    print(f"STDERR: {stderr}")
                return False
            
        except Exception as e:
            print(f"❌ FFmpeg recording failed: {e}")
            return False
    
    def stop_recording(self):
        """Stop recording with proper file finalization"""
        print("Stopping recording...")
        
        self.can_finish_early = False
        
        if self.recording_process:
            try:
                # Send SIGTERM for graceful shutdown
                print("Sending termination signal to FFmpeg...")
                self.recording_process.terminate()
                
                # Wait longer for proper file finalization
                try:
                    stdout, stderr = self.recording_process.communicate(timeout=10)
                    print("✅ FFmpeg recording stopped gracefully")
                    
                    # Print any error info for debugging
                    if stderr and "error" in stderr.lower():
                        print(f"FFmpeg stderr: {stderr}")
                        
                except subprocess.TimeoutExpired:
                    print("⚠️  FFmpeg didn't stop gracefully, force killing")
                    self.recording_process.kill()
                    self.recording_process.communicate()
                
            except Exception as e:
                print(f"❌ Error stopping FFmpeg: {e}")
            
            self.recording_process = None
            
            # Wait a moment for file system to finalize
            time.sleep(1)
        
        # Check if file was created and is valid
        if self.current_recording_path and os.path.exists(self.current_recording_path):
            file_size = os.path.getsize(self.current_recording_path)
            
            if file_size > 1000:  # At least 1KB
                # Double-check the file is valid
                if self.is_video_file_valid(self.current_recording_path):
                    print(f"✅ Recording saved and validated: {self.current_recording_path} ({file_size} bytes)")
                    self.recording_status = f"Saved: {os.path.basename(self.current_recording_path)}"
                    
                    # Rescan videos to include the new one
                    self.scan_recorded_videos()
                else:
                    print(f"❌ Recording file is corrupted, removing: {self.current_recording_path}")
                    try:
                        os.remove(self.current_recording_path)
                    except:
                        pass
                    self.recording_status = "Recording corrupted, removed"
            else:
                print(f"❌ Recording file too small ({file_size} bytes), removing")
                try:
                    os.remove(self.current_recording_path)
                except:
                    pass
                self.recording_status = "Recording failed - file too small"
        else:
            print("❌ Recording file not found")
            self.recording_status = "Recording failed - no file created"
        
        self.current_recording_path = None
    
    def get_camera_frame_for_display(self):
        """Get camera frame for live preview - full window size"""
        if not self.camera:
            return None
            
        try:
            ret, frame = self.camera.read()
            if ret:
                # Flip horizontally for mirror effect
                frame = cv2.flip(frame, 1)
                
                # Resize to full window size
                frame = cv2.resize(frame, (self.screen_width, self.screen_height))
                
                # Convert BGR to RGB for pygame
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Transpose for pygame (width, height) format
                frame_rgb = np.transpose(frame_rgb, (1, 0, 2))
                
                return frame_rgb
        except Exception as e:
            print(f"Frame display error: {e}")
        
        return None
    
    def get_video_info(self, video_path):
        """Get video duration and FPS"""
        try:
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            duration = frame_count / fps if fps > 0 else 0
            cap.release()
            return duration, fps
        except:
            return 0, 30
    
    def start_video_playback(self, video_path):
        """Start playing a video with audio - simplified approach"""
        try:
            print(f"Starting playback: {os.path.basename(video_path)}")
            
            # Validate file first
            if not self.is_video_file_valid(video_path):
                print(f"❌ Video file is invalid: {video_path}")
                return False
            
            # Stop any current playback
            self.stop_current_playback()
            
            # Open video file
            self.playback_cap = cv2.VideoCapture(video_path)
            if not self.playback_cap.isOpened():
                print(f"❌ Could not open video: {video_path}")
                return False
            
            # Get video properties
            self.video_fps = self.playback_cap.get(cv2.CAP_PROP_FPS) or 30
            frame_count = self.playback_cap.get(cv2.CAP_PROP_FRAME_COUNT)
            duration = frame_count / self.video_fps if self.video_fps > 0 else 0
            
            print(f"Video info: {self.video_fps:.1f} fps, {duration:.1f} seconds")
            
            # Use the exact command that works manually
            try:
                cmd = [
                    'ffplay',
                    '-i', video_path,
                    '-vn',  # No video, audio only
                    '-nodisp',  # No display
                    '-autoexit',  # Exit when finished
                    '-loglevel', 'verbose'  # Same as manual test
                ]
                
                print(f"Audio command: {' '.join(cmd)}")
                # Don't capture stdout/stderr - let audio play directly to system
                self.audio_process = subprocess.Popen(cmd)
                
                # Give it time to start
                time.sleep(1)
                
                if self.audio_process.poll() is None:
                    print("✅ Audio process started - should be playing now")
                    print("🔊 Audio should be audible (same command that worked manually)")
                else:
                    print("❌ Audio process died immediately")
                    self.audio_process = None
                    
            except Exception as e:
                print(f"❌ Could not start audio: {e}")
                self.audio_process = None
            
            # Set timing
            self.video_start_time = time.time()
            self.current_playback_video = video_path
            
            return True
            
        except Exception as e:
            print(f"❌ Video playback failed: {e}")
            return False
    
    def stop_current_playback(self):
        """Stop current video and audio playback"""
        if self.playback_cap:
            self.playback_cap.release()
            self.playback_cap = None
        
        if self.audio_process:
            try:
                self.audio_process.terminate()
                self.audio_process.wait(timeout=1)
            except:
                try:
                    self.audio_process.kill()
                except:
                    pass
            self.audio_process = None
        
        self.current_playback_video = None
        self.video_start_time = None
    
    def get_current_playback_frame(self):
        """Get current frame from playback video with real-time sync"""
        if not self.recorded_videos or self.switching_video:
            return None
        
        # Start video if none is playing
        if not self.current_playback_video:
            if not self.start_video_playback(self.recorded_videos[self.current_playback_index]):
                return None
        
        # Get frame from video
        if self.playback_cap and self.video_start_time:
            # Calculate which frame we should be at based on real time
            elapsed_time = time.time() - self.video_start_time
            target_frame = int(elapsed_time * self.video_fps)
            
            # Get current frame position
            current_frame = int(self.playback_cap.get(cv2.CAP_PROP_POS_FRAMES))
            
            # Skip frames if we're behind, or wait if we're ahead
            if target_frame > current_frame + 5:  # If we're way behind, skip frames
                self.playback_cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
            elif target_frame < current_frame - 1:  # If we're ahead, wait
                return getattr(self, 'last_playback_frame', None)
            
            ret, frame = self.playback_cap.read()
            if ret:
                # Flip for mirror effect
                frame = cv2.flip(frame, 1)
                
                # Resize to full window size
                frame = cv2.resize(frame, (self.screen_width, self.screen_height))
                
                # Convert BGR to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Transpose for pygame
                frame_rgb = np.transpose(frame_rgb, (1, 0, 2))
                
                # Cache this frame
                self.last_playback_frame = frame_rgb
                return frame_rgb
            else:
                # Video ended, switch to next
                self.switch_to_next_video()
                return None
        
        return None
    
    def switch_to_next_video(self):
        """Switch to the next video in the playlist"""
        if not self.recorded_videos or self.switching_video:
            return
        
        self.switching_video = True
        
        # Stop current playback
        self.stop_current_playback()
        
        # Move to next video
        self.current_playback_index = (self.current_playback_index + 1) % len(self.recorded_videos)
        
        # Small delay to ensure clean transition
        time.sleep(0.1)
        
        self.switching_video = False
        
        print(f"Switching to video {self.current_playback_index + 1} of {len(self.recorded_videos)}")
    
    def check_if_video_ended(self):
        """Check if current video has ended and handle audio sync"""
        if self.audio_process and self.audio_process.poll() is not None:
            # Audio process ended, switch to next video
            print("Audio ended, switching to next video")
            self.switch_to_next_video()
            return True
        return False
        """State machine"""
    def advance_state(self):
        """State machine"""
        # Stop any video playback when leaving idle
        if self.current_state == State.IDLE:
            self.stop_current_playback()
        
        # Clean up custom video caps when changing states
        if self.prompt_video_cap:
            self.prompt_video_cap.release()
            self.prompt_video_cap = None
        if self.timer_video_cap:
            self.timer_video_cap.release()
            self.timer_video_cap = None
        if self.thankyou_video_cap:
            self.thankyou_video_cap.release()
            self.thankyou_video_cap = None
        
        if self.current_state == State.IDLE:
            self.current_state = State.PROMPT
        elif self.current_state == State.PROMPT:
            self.current_state = State.RECORDING
            self.start_recording()
        elif self.current_state == State.RECORDING:
            self.current_state = State.THANKYOU
            self.stop_recording()
        elif self.current_state == State.THANKYOU:
            self.current_state = State.IDLE
        
        self.state_start_time = time.time()
        self.custom_video_start_time = None  # Reset custom video timing
        print(f"State: {self.current_state.value}")
    
    def check_state_timeout(self):
        """Auto-advance states"""
        elapsed = time.time() - self.state_start_time
        
        if self.current_state == State.PROMPT and elapsed >= self.PROMPT_TIME:
            self.advance_state()
        elif self.current_state == State.RECORDING and elapsed >= self.RECORDING_TIME:
            self.advance_state()
        elif self.current_state == State.THANKYOU and elapsed >= self.THANKYOU_TIME:
            self.advance_state()
    
    def render(self):
        """Render with full window video and audio playback"""
        self.screen.fill(self.BLACK)
        
        if self.current_state == State.IDLE:
            # Check if video ended
            self.check_if_video_ended()
            
            # Show recorded videos if available, otherwise camera preview
            playback_frame = self.get_current_playback_frame()
            
            if playback_frame is not None:
                # Show recorded video playback - full window
                try:
                    playback_surface = pygame.surfarray.make_surface(playback_frame)
                    self.screen.blit(playback_surface, (0, 0))
                    
                    # Overlay: current video info
                    if self.recorded_videos and self.current_playback_video:
                        current_video = os.path.basename(self.current_playback_video)
                        video_text = self.font_small.render(f"Playing: {current_video}", True, self.WHITE)
                        # Add semi-transparent background
                        text_bg = pygame.Surface((video_text.get_width() + 20, video_text.get_height() + 10))
                        text_bg.set_alpha(128)
                        text_bg.fill(self.BLACK)
                        self.screen.blit(text_bg, (10, 10))
                        self.screen.blit(video_text, (20, 15))
                        
                        # Show video counter
                        counter_text = self.font_small.render(f"Video {self.current_playback_index + 1} of {len(self.recorded_videos)}", True, self.WHITE)
                        counter_bg = pygame.Surface((counter_text.get_width() + 20, counter_text.get_height() + 10))
                        counter_bg.set_alpha(128)
                        counter_bg.fill(self.BLACK)
                        self.screen.blit(counter_bg, (10, 40))
                        self.screen.blit(counter_text, (20, 45))
                    
                except Exception as e:
                    print(f"Playback display error: {e}")
                    # Fallback
                    self.render_idle_fallback()
            else:
                # No recordings - show camera preview and instructions
                self.render_idle_fallback()
            
            # Instructions overlay
            instruction_text = self.font_medium.render("Press SPACE to record your response", True, self.WHITE)
            text_bg = pygame.Surface((instruction_text.get_width() + 20, instruction_text.get_height() + 10))
            text_bg.set_alpha(128)
            text_bg.fill(self.BLACK)
            self.screen.blit(text_bg, (10, self.screen_height - 60))
            self.screen.blit(instruction_text, (20, self.screen_height - 55))
            
        elif self.current_state == State.PROMPT:
            # Try to show custom prompt video, fallback to text
            if not self.prompt_video_cap:
                self.prompt_video_cap = self.load_custom_video('prompt')
            
            if self.prompt_video_cap:
                # Show custom prompt video
                frame = self.get_custom_video_frame(self.prompt_video_cap)
                if frame is not None:
                    try:
                        video_surface = pygame.surfarray.make_surface(frame)
                        self.screen.blit(video_surface, (0, 0))
                    except:
                        # Fallback to text if video fails
                        self.render_prompt_text()
                else:
                    # Video ended or failed
                    self.render_prompt_text()
            else:
                # No custom video, show text
                self.render_prompt_text()
            
        elif self.current_state == State.RECORDING:
            # Check for custom timer video
            if not self.timer_video_cap:
                self.timer_video_cap = self.load_custom_video('timer')
            
            # Show live camera feed first
            camera_frame = self.get_camera_frame_for_display()
            
            if camera_frame is not None:
                try:
                    camera_surface = pygame.surfarray.make_surface(camera_frame)
                    self.screen.blit(camera_surface, (0, 0))
                    
                    # Overlay timer video if available
                    if self.timer_video_cap:
                        timer_frame = self.get_custom_video_frame(self.timer_video_cap)
                        if timer_frame is not None:
                            # Overlay timer in corner or blend
                            timer_surface = pygame.surfarray.make_surface(timer_frame)
                            timer_surface.set_alpha(180)  # Semi-transparent
                            self.screen.blit(timer_surface, (0, 0))
                    
                    # Recording indicator
                    record_text = self.font_large.render("● RECORDING", True, self.RED)
                    text_bg = pygame.Surface((record_text.get_width() + 20, record_text.get_height() + 10))
                    text_bg.set_alpha(128)
                    text_bg.fill(self.BLACK)
                    self.screen.blit(text_bg, (10, 10))
                    self.screen.blit(record_text, (20, 15))
                    
                except Exception as e:
                    print(f"Live feed error: {e}")
                    self.screen.fill(self.RED)
                    text = self.font_large.render("RECORDING", True, self.WHITE)
                    text_rect = text.get_rect(center=(self.screen_width//2, self.screen_height//2))
                    self.screen.blit(text, text_rect)
            else:
                # No camera fallback
                self.screen.fill(self.RED)
                text = self.font_large.render("RECORDING", True, self.WHITE)
                text_rect = text.get_rect(center=(self.screen_width//2, self.screen_height//2))
                self.screen.blit(text, text_rect)
            
            # Time remaining overlay
            elapsed = time.time() - self.state_start_time
            remaining = max(0, self.RECORDING_TIME - elapsed)
            countdown = self.font_medium.render(f"Time left: {remaining:.1f}s", True, self.WHITE)
            
            text_bg = pygame.Surface((countdown.get_width() + 20, countdown.get_height() + 10))
            text_bg.set_alpha(128)
            text_bg.fill(self.BLACK)
            self.screen.blit(text_bg, (10, self.screen_height - 80))
            self.screen.blit(countdown, (20, self.screen_height - 75))
            
            # Early finish instruction
            if self.can_finish_early:
                finish_text = self.font_small.render("Press SPACE again to finish early", True, self.WHITE)
                text_bg2 = pygame.Surface((finish_text.get_width() + 20, finish_text.get_height() + 10))
                text_bg2.set_alpha(128)
                text_bg2.fill(self.BLACK)
                self.screen.blit(text_bg2, (10, self.screen_height - 120))
                self.screen.blit(finish_text, (20, self.screen_height - 115))
            
        elif self.current_state == State.THANKYOU:
            # Try to show custom thank you video, fallback to text
            if not self.thankyou_video_cap:
                self.thankyou_video_cap = self.load_custom_video('thankyou')
            
            if self.thankyou_video_cap:
                # Show custom thank you video
                frame = self.get_custom_video_frame(self.thankyou_video_cap)
                if frame is not None:
                    try:
                        video_surface = pygame.surfarray.make_surface(frame)
                        self.screen.blit(video_surface, (0, 0))
                    except:
                        # Fallback to text
                        self.render_thankyou_text()
                else:
                    # Video ended or failed
                    self.render_thankyou_text()
            else:
                # No custom video, show text
                self.render_thankyou_text()
        
        # Debug info overlay (small, bottom right)
        debug_texts = [
            f"State: {self.current_state.value}",
            f"Videos: {len(self.recorded_videos)}",
            f"Status: {self.recording_status}"
        ]
        
        if self.current_state == State.IDLE and self.audio_process:
            debug_texts.append("🔊 Audio playing")
        
        debug_y = self.screen_height - (len(debug_texts) * 20) - 10
        for text in debug_texts:
            debug_surface = self.font_small.render(text, True, self.WHITE)
            text_bg = pygame.Surface((debug_surface.get_width() + 10, debug_surface.get_height() + 5))
            text_bg.set_alpha(128)
            text_bg.fill(self.BLACK)
            self.screen.blit(text_bg, (self.screen_width - debug_surface.get_width() - 15, debug_y))
            self.screen.blit(debug_surface, (self.screen_width - debug_surface.get_width() - 10, debug_y + 2))
            debug_y += 20
        
        pygame.display.flip()
    
    def render_prompt_text(self):
        """Fallback text rendering for prompt state"""
        self.screen.fill(self.BLACK)
        prompt_text = self.font_large.render("What does home mean to you?", True, self.WHITE)
        prompt_rect = prompt_text.get_rect(center=(self.screen_width//2, self.screen_height//2))
        self.screen.blit(prompt_text, prompt_rect)
        
        elapsed = time.time() - self.state_start_time
        remaining = max(0, self.PROMPT_TIME - elapsed)
        countdown = self.font_medium.render(f"Recording starts in: {remaining:.1f}s", True, self.WHITE)
        countdown_rect = countdown.get_rect(center=(self.screen_width//2, self.screen_height//2 + 60))
        self.screen.blit(countdown, countdown_rect)
    
    def render_thankyou_text(self):
        """Fallback text rendering for thank you state"""
        self.screen.fill(self.GREEN)
        text = self.font_large.render("Thank you for sharing!", True, self.WHITE)
        text_rect = text.get_rect(center=(self.screen_width//2, self.screen_height//2))
        self.screen.blit(text, text_rect)
    
    def render_idle_fallback(self):
        """Fallback rendering for idle state when no videos"""
        camera_frame = self.get_camera_frame_for_display()
        
        if camera_frame is not None:
            # Show full window camera preview
            camera_surface = pygame.surfarray.make_surface(camera_frame)
            self.screen.blit(camera_surface, (0, 0))
        else:
            # No camera fallback
            self.screen.fill(self.BLACK)
            text = self.font_large.render("Press SPACE to start", True, self.WHITE)
            text_rect = text.get_rect(center=(self.screen_width//2, self.screen_height//2))
            self.screen.blit(text, text_rect)
    
    def handle_events(self):
        """Handle input with early finish capability"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    if self.current_state == State.IDLE:
                        self.advance_state()
                    elif self.current_state == State.RECORDING and self.can_finish_early:
                        # Finish recording early
                        print("Finishing recording early...")
                        self.advance_state()
                elif event.key == pygame.K_r:
                    # Reset to idle
                    if self.recording_process:
                        self.stop_recording()
                    self.current_state = State.IDLE
                    self.state_start_time = time.time()
                    self.can_finish_early = False
                elif event.key == pygame.K_ESCAPE:
                    return False
        return True
    
    def cleanup(self):
        """Cleanup"""
        # Stop video playback
        self.stop_current_playback()
        
        if self.recording_process:
            try:
                self.recording_process.terminate()
                self.recording_process.wait(timeout=2)
            except:
                try:
                    self.recording_process.kill()
                except:
                    pass
        
        if self.camera:
            self.camera.release()
            
        cv2.destroyAllWindows()
        pygame.quit()
    
    def run(self):
        """Main loop"""
        print("\n=== CONTROLS ===")
        print("SPACE: Start recording sequence")
        print("SPACE (during recording): Finish early")
        print("R: Reset to idle")
        print("ESC: Quit")
        print("\n⚠️  IMPORTANT: FFmpeg is required for audio recording!")
        print("Install with: brew install ffmpeg")
        print("================\n")
        
        clock = pygame.time.Clock()
        running = True
        
        try:
            while running:
                running = self.handle_events()
                self.check_state_timeout()
                self.render()
                clock.tick(60)  # 60 FPS for smooth display
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            self.cleanup()

if __name__ == "__main__":
    app = HomeInstallation()
    app.run()