#! /usr/bin/env python3

import docopt
import math
import sys


__doc__ = '''\
Usage:
    armor.py efficient <alphabet_size> [--bound=<n>]
    armor.py encode [--alphabet=<str>] [--base64] [--block=<n>] [<bytes>]
    armor.py decode [--alphabet=<str>] [--base64] [--block=<n>] [<chars>]
    armor.py armor [--alphabet=<str>] [--base64] [--block=<n>] [<bytes>]
    armor.py dearmor [--alphabet=<str>] [--base64] [--block=<n>] [<chars>]
'''


b64alphabet = \
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

b62alphabet = \
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def min_chars_size(alphabet_size, bytes_size):
    '''The most bytes we can represent satisfies this:
           256 ^ bytes_size <= alphabet_size ^ chars_size
       Take the log_2 of both sides:
           8 * bytes_size <= log_2(alphabet_size) * chars_size
        Solve for the minimum chars_size:
    '''
    return math.ceil(8 * bytes_size / math.log(alphabet_size, 2))


def max_bytes_size(alphabet_size, chars_size):
    '''The most bytes we can represent satisfies this:
           256 ^ bytes_size <= alphabet_size ^ chars_size
       Take the log_2 of both sides:
           8 * bytes_size <= log_2(alphabet_size) * chars_size
        Solve for the maximum bytes_size:
    '''
    return math.floor(math.log(alphabet_size, 2) / 8 * chars_size)


def efficient_chars_sizes(alphabet_size, chars_size_upper_bound):
    out = []
    max_efficiency = 0
    for chars_size in range(1, chars_size_upper_bound):
        bytes_size = max_bytes_size(alphabet_size, chars_size)
        efficiency = bytes_size / chars_size
        # This check also excludes sizes too small to encode a single byte.
        if efficiency > max_efficiency:
            out.append((chars_size, bytes_size, efficiency))
            max_efficiency = efficiency
    return out


def print_efficient_chars_sizes(alphabet_size, chars_size_upper_bound):
    print("efficient block sizes for alphabet size", alphabet_size)
    for chars_size, bytes_size, efficiency in \
            efficient_chars_sizes(alphabet_size, chars_size_upper_bound):
        print("{:2d} chars: {:2d} bytes ({:.2f}%)".format(
            chars_size, bytes_size, 100 * efficiency))


def extra_bits(alphabet_size, chars_size, bytes_size):
    '''In order to be compatible with Base64, when we write a partial block, we
    need to shift as far left as we can. Figure out how many whole extra bits
    the encoding space has relative to the bytes coming in.'''
    total_bits = math.floor(math.log(alphabet_size, 2) * chars_size)
    return total_bits - 8*bytes_size


def encode_to_chars(alphabet, bytes_block):
    # Figure out how wide the chars block needs to be, and how many extra bits
    # we have.
    chars_size = min_chars_size(len(alphabet), len(bytes_block))
    extra = extra_bits(len(alphabet), chars_size, len(bytes_block))
    # Convert the bytes into an integer, big-endian.
    bytes_int = int.from_bytes(bytes_block, byteorder='big')
    # Shift left by the extra bits.
    bytes_int <<= extra
    # Convert the result into our base.
    places = []
    for place in range(chars_size):
        rem = bytes_int % len(alphabet)
        places.insert(0, rem)
        bytes_int //= len(alphabet)
    return "".join(alphabet[p] for p in places)


def get_char_index(alphabet, char):
    'This is the same as alphabet.index(char), but with more helpful errors.'
    try:
        return alphabet.index(char)
    except ValueError:
        raise ValueError("Could not find {} in alphabet {}.".format(
            repr(char), repr(alphabet)))


def decode_from_chars(alphabet, chars_block):
    # Figure out how many bytes we have, and how many extra bits they'll have
    # been shifted by.
    bytes_size = max_bytes_size(len(alphabet), len(chars_block))
    extra = extra_bits(len(alphabet), len(chars_block), bytes_size)
    # Convert the chars to an integer.
    bytes_int = get_char_index(alphabet, chars_block[0])
    for c in chars_block[1:]:
        bytes_int *= len(alphabet)
        bytes_int += get_char_index(alphabet, c)
    # Shift right by the extra bits.
    bytes_int >>= extra
    # Convert the result to bytes, big_endian.
    return bytes_int.to_bytes(bytes_size, byteorder='big')


def chunk_bytes(b, size):
    assert size > 0
    chunks = []
    i = 0
    while i < len(b):
        chunks.append(b[i:i+size])
        i += size
    return chunks


def chunk_string(s, size):
    'Skip over whitespace when assembling chunks.'
    assert size > 1
    chunks = []
    chunk = ''
    for c in s:
        if c.isspace():
            continue
        chunk += c
        if len(chunk) == size:
            chunks.append(chunk)
            chunk = ''
    if chunk:
        chunks.append(chunk)
    return chunks


def read_between_periods(s):
    start = s.find('.')
    if start == -1:
        raise Exception("No period found in input.")
    end = s.find('.', start+1)
    if end == -1:
        raise Exception("No closing period found in input.")
    return s[start+1:end]


def get_block_size(args):
    block_size = 32
    if args['--base64']:
        block_size = 3
    if args['--block']:
        block_size = int(args['--block'])
    return block_size


def get_alphabet(args):
    alphabet = b62alphabet
    if args['--base64']:
        alphabet = b64alphabet
    if args['--alphabet']:
        alphabet = args['--alphabet']
    return alphabet


def do_efficient(args):
    if args['--bound'] is None:
        upper_bound = 50
    else:
        upper_bound = int(args['--bound'])
    alphabet_size = int(args['<alphabet_size>'])
    print_efficient_chars_sizes(alphabet_size, upper_bound)


def do_encode(args):
    if args['<bytes>'] is not None:
        bytes_in = args['<bytes>'].encode()
    else:
        bytes_in = sys.stdin.buffer.read()
    chunks = chunk_bytes(bytes_in, get_block_size(args))
    print(' '.join(encode_to_chars(
        get_alphabet(args), chunk) for chunk in chunks))


def do_decode(args):
    if args['<chars>'] is not None:
        chars_in = args['<chars>']
    else:
        chars_in = sys.stdin.read()
    alphabet = get_alphabet(args)
    char_block_size = min_chars_size(len(alphabet), get_block_size(args))
    chunks = chunk_string(chars_in, char_block_size)
    for chunk in chunks:
        sys.stdout.buffer.write(decode_from_chars(alphabet, chunk))


def main():
    args = docopt.docopt(__doc__)

    if args['efficient']:
        do_efficient(args)
    elif args['encode']:
        do_encode(args)
    elif args['decode']:
        do_decode(args)

if __name__ == '__main__':
    main()
