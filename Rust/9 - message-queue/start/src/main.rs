use sdl2::event::Event;
use sdl2::mixer;

mod view;
use view::board_view::Renderer;

mod model;
use model::game::GameState;

fn main() -> Result<(), String> {

    let screen_width = 800;
    let screen_height = 600;
    
    let sdl_context = sdl2::init()?;
    let video_subsystem = sdl_context.video()?;
    let window = video_subsystem.window("Rust!", screen_width, screen_height)
        .build()
        .unwrap();
    
    let mut canvas = window.into_canvas()
        .build()
        .unwrap();

    let texture_creator = canvas.texture_creator();

    mixer::open_audio(44100, mixer::DEFAULT_FORMAT, 2, 4096)?;
    let do_sound = mixer::Chunk::from_file("sfx/click_on.wav")?;
    let undo_sound = mixer::Chunk::from_file("sfx/click_off.wav")?;
    let channel = mixer::Channel(0);
    
    let board_view: Renderer = Renderer::new(
        screen_width, screen_height, &texture_creator
    );

    let mut game_state: GameState = GameState::new();

    let mut running = true;
    let mut event_queue = sdl_context.event_pump().unwrap();

    while running {

        for event in event_queue.poll_iter() {

            match event {
                Event::Quit {..} => {
                    running = false;
                },

                Event::MouseButtonDown { x , y, .. } => {
                    let row: usize = (5 * y / board_view.screen_area.h).try_into().unwrap();
                    let col: usize = (5 * x / board_view.screen_area.w).try_into().unwrap();
                    game_state.handle_click(row, col);
                    mixer::Channel::play(channel, &do_sound, 1)?;
                },
                Event::KeyDown { keycode, .. } => {
                    if keycode.unwrap() == sdl2::keyboard::Keycode::U {
                        game_state.undo_action();
                        mixer::Channel::play(channel, &undo_sound, 1)?;
                    }
                    else if keycode.unwrap() == sdl2::keyboard::Keycode::R {
                        game_state.redo_action();
                        mixer::Channel::play(channel, &do_sound, 1)?;
                    }
                }

                _ => {}
            }
        }

        board_view.render(&mut canvas, &game_state.board);
        canvas.present();
    }

    Ok(())
}
