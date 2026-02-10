# 将棋 - Shogi (Japanese Chess)

A complete browser-based Shogi game with AI opponent, built as a single HTML file with no dependencies.

## How to Play

Simply open `index.html` in any modern web browser. No server or installation required.

## Features

- **Full Shogi rules**: All piece types with correct movement, promotion, captured piece drops, check/checkmate detection
- **AI opponent**: Three difficulty levels (初級/中級/上級) with minimax + alpha-beta pruning
- **Traditional styling**: Wood-themed board with authentic kanji piece characters (玉/飛/角/金/銀/桂/香/歩)
- **Sound effects**: Subtle audio feedback for moves and captures
- **Move history**: Japanese notation (棋譜) with ☗/☖ markers
- **Undo support**: Take back moves (待った)
- **Responsive design**: Works on desktop and mobile
- **Promotion dialog**: Choose whether to promote pieces (成る/不成)

## Piece Guide

| Piece | Kanji | Promoted | Movement |
|-------|-------|----------|----------|
| King | 玉/王 | - | One step any direction |
| Rook | 飛 | 龍 (Dragon) | Slides orthogonally (+diagonal step when promoted) |
| Bishop | 角 | 馬 (Horse) | Slides diagonally (+orthogonal step when promoted) |
| Gold | 金 | - | One step forward/sideways/backward |
| Silver | 銀 | 全 | One step forward/diagonally |
| Knight | 桂 | 圭 | L-shape forward only |
| Lance | 香 | 杏 | Slides forward only |
| Pawn | 歩 | と (Tokin) | One step forward |

## Controls

- **新局 (New)**: Start a new game
- **待った (Undo)**: Take back your last move
- **初級/中級/上級**: Set AI difficulty
