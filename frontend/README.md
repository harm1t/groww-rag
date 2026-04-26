# PPFAS RAG Frontend

Next.js frontend for the PPFAS Mutual Fund FAQ RAG Assistant, built with the Fintech Clarity design system.

## Design System

The frontend uses the "Fintech Clarity" design system with:
- **Primary Color**: Green (#00D09C) for growth indicators and CTAs
- **Secondary**: Deep Navy (#0F172A) for authority and weight
- **Typography**: Inter font family for maximum legibility
- **Spacing**: 8px baseline rhythm with 12-column fluid grid
- **Elevation**: Tonal layers with ambient shadows

## Tech Stack

- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Icons**: Lucide React

## Getting Started

### Installation

```bash
cd frontend
npm install
```

### Environment Variables

Create a `.env.local` file:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Development

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### Build

```bash
npm run build
npm start
```

## Project Structure

```
frontend/
├── src/
│   ├── app/
│   │   ├── globals.css       # Global styles with design system
│   │   ├── layout.tsx        # Root layout
│   │   └── page.tsx          # Main page
│   └── components/
│       └── ChatInterface.tsx # Chat interface component
├── tailwind.config.ts        # Tailwind with design system colors
├── tsconfig.json
└── package.json
```

## Features

- **Chat Interface**: Real-time chat with the RAG backend
- **Welcome Screen**: Example questions for quick start
- **Message Formatting**: Automatic citation and source link formatting
- **Typing Indicators**: Visual feedback during API calls
- **Responsive Design**: Works on mobile and desktop
- **Design System**: Consistent styling with Fintech Clarity theme

## API Integration

The frontend connects to the backend API using the `NEXT_PUBLIC_API_URL` environment variable:

- **Create Thread**: `POST /threads`
- **Send Message**: `POST /threads/{thread_id}/messages`
- **Get Messages**: `GET /threads/{thread_id}/messages`
- **List Threads**: `GET /threads`

## Deployment

See [deployment.md](../docs/deployment.md) for deployment instructions using Vercel.
