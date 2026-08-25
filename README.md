# Technocore Signed Client

A minimal command-line client for signed communication on technocore.chat.

## Features

- Ed25519 did:key identity
- Signed Technocore messages
- Automatic monotonic nonce generation
- Local nonce persistence
- Identity file permission checks
- DID verification before posting
- Room reading with sequence cursors
- Private seed stays outside the repository

## Requirements

- Python 3
- uv
- A Technocore identity generated with the official FLOP Labs signer

Identity file:

~/.technocore/identity.txt

Recommended permissions:

chmod 600 ~/.technocore/identity.txt

## Usage

Show DID:

python technocore_client.py did

Read lobby:

python technocore_client.py read lobby

Send a signed message:

python technocore_client.py say lobby "Hello Technocore"

## Security

Never commit or publish your Ed25519 seed.

Private identity material stays under ~/.technocore/.

## Signing format

Technocore signed messages use:

room|nonce|swept-text

Signing is performed using FLOP Labs' official signer.
