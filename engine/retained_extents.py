"""Offline, bounded reconstruction from retained, uncompressed Btrfs extents.

This module never opens a device, connects to a NAS, or overwrites an input.
Allocation expansion is a historical mapping hypothesis, not an independent
proof of file identity. Generation, all plaintext overlaps, block checksums
and external format validation are required before promoting an output.
"""
import hashlib
from functools import lru_cache

BLOCK = 4096
CHUNK = 1024 * 1024
FACTORS = {10:4, 15:5, 20:7, 25:9, 30:10, 35:12,
           40:14, 50:10, 60:20, 70:23, 80:27}


class Rejected(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Rejected(message)


def merge(ranges):
    out = []
    for a, b in sorted(ranges):
        require(0 <= a <= b, 'invalid_range')
        if a == b:
            continue
        if out and a <= out[-1][1]:
            out[-1][1] = max(b, out[-1][1])
        else:
            out.append([a, b])
    return out


def complement(ranges, size):
    out, pos = [], 0
    for a, b in merge(ranges):
        require(b <= size, 'range_outside_file')
        if a > pos:
            out.append([pos, a])
        pos = b
    if pos < size:
        out.append([pos, size])
    return out


def intersect(a, b, c, d):
    return max(a, c), min(b, d)


def parse_footer(footer, ciphertext_size, marker=None):
    require(len(footer) == 588, 'footer_length')
    require(marker is not None and footer[568:572].hex() == marker, 'footer_marker')
    require(footer[574:576] == b'\x20\x00', 'unsupported_crypto')
    n = int.from_bytes(footer[580:588], 'little')
    require(n > 0 and n + 588 == ciphertext_size, 'footer_size')
    mode, pct = footer[572:574]
    if mode in (0x24, 0x26):
        require(pct == 0, 'unexpected_parameter')
        ranges = [[0, n if mode == 0x24 else min(n, 1 << 20)]]
    elif mode == 0x25 and pct in FACTORS:
        length = (n // 100) * FACTORS[pct]
        count = 5 if pct == 50 else 3
        gap = length if pct == 50 else (n - 3 * length) // 2
        ranges = [[i*(length+gap), i*(length+gap)+length] for i in range(count)]
    else:
        raise Rejected('unsupported_mode_or_parameter')
    require(all(0 <= a <= b <= n for a, b in ranges), 'invalid_formula')
    ranges = merge(ranges)
    return {'size':n, 'mode':mode, 'percent':pct, 'encrypted':ranges,
            'plaintext':complement(ranges, n), 'marker':marker}


def build_plan(size, encrypted, items):
    """Plan [0,size) using live references only; never bridge unknown gaps."""
    require(isinstance(size, int) and size > 0, 'invalid_size')
    enc = merge(encrypted)
    plain = complement(enc, size)
    require(0 < len(items) <= 10000, 'extent_count')
    items = sorted((dict(it) for it in items), key=lambda x:x['pos'])
    end = 0
    for it in items:
        require(all(isinstance(it.get(k), int) and it[k] >= 0
                    for k in ('pos','gen','type','comp','bytenr','dnum','eoff','num')), 'extent_fields')
        require(it['type'] == 1 and it['comp'] == 0 and it['bytenr'] > 0, 'unsupported_extent_layout')
        require(it.get('enc',0) == 0 and it.get('oenc',0) == 0, 'encoded_extent')
        require(all(it[k] % BLOCK == 0 for k in ('pos','bytenr','dnum','eoff','num')), 'unaligned_extent')
        require(it['num'] > 0 and it['eoff'] + it['num'] <= it['dnum'], 'extent_bounds')
        require(it['pos'] == end, 'current_mapping_gap_or_overlap')
        end = it['pos'] + it['num']
    require(end >= size, 'current_mapping_incomplete')
    candidates = {}
    for it in items:
        anchors = [list(intersect(a,b,it['pos'],it['pos']+it['num'])) for a,b in plain]
        anchors = [v for v in anchors if v[0] < v[1]]
        if not anchors:
            continue
        base = it['pos'] - it['eoff']
        tag = (it['bytenr'], base, it['dnum'], it['gen'])
        if tag not in candidates:
            candidates[tag] = {'id':len(candidates), 'logical':it['bytenr'],
                'file_base':base, 'length':it['dnum'], 'generation':it['gen'], 'live_anchors':[]}
        candidates[tag]['live_anchors'].extend(anchors)
    candidates = list(candidates.values())
    boundaries = {0, size}
    for a,b in enc:
        boundaries.update((a,b))
    for it in items:
        boundaries.update(x for x in (it['pos'],it['pos']+it['num']) if 0 < x < size)
    for c in candidates:
        boundaries.update(x for x in (c['file_base'], c['file_base']+c['length']) if 0 < x < size)
        c['live_anchors'] = merge(c['live_anchors'])
        c['plain_checks'] = [list(intersect(a,b,max(0,c['file_base']),min(size,c['file_base']+c['length']))) for a,b in plain]
        c['plain_checks'] = [v for v in c['plain_checks'] if v[0] < v[1]]
    spans = []
    points = sorted(boundaries)
    for a,b in zip(points, points[1:]):
        if not any(s <= a and b <= e for s,e in enc):
            spans.append({'start':a,'end':b,'kind':'current'})
            continue
        current = next(it for it in items if it['pos'] <= a < it['pos']+it['num'])
        eligible = [c for c in candidates if c['file_base'] <= a and b <= c['file_base']+c['length']
                    and c['generation'] < current['gen'] and c['logical'] != current['bytenr']]
        # Multiple records with the same affine mapping are harmless; different
        # mappings must not be arbitrarily selected, even if file headers look good.
        maps = {c['logical']-c['file_base'] for c in eligible}
        if len(maps) == 1:
            chosen = min(eligible, key=lambda c:c['id'])
            spans.append({'start':a,'end':b,'kind':'old','candidate_id':chosen['id'],
                          'logical':chosen['logical']+a-chosen['file_base']})
        else:
            spans.append({'start':a,'end':b,'kind':'ambiguous' if maps else 'missing',
                          'candidate_ids':[c['id'] for c in eligible]})
    missing = sum(s['end']-s['start'] for s in spans if s['kind']=='missing')
    ambiguous = sum(s['end']-s['start'] for s in spans if s['kind']=='ambiguous')
    return {'schema':1,'size':size,'encrypted':enc,'plaintext':plain,'candidates':candidates,
            'spans':spans,'missing_bytes':missing,'ambiguous_bytes':ambiguous,
            'status':'candidate_complete' if not missing and not ambiguous else 'incomplete',
            'validation_required':['captured_current_mapping_matches','unchanged_source_receipt',
                                   'all_plaintext_overlaps','all_used_old_block_checksums','full_format_validation']}


_CRC = []
for _i in range(256):
    _v = _i
    for _ in range(8):
        _v = (_v >> 1) ^ (0x82F63B78 if _v & 1 else 0)
    _CRC.append(_v)


def crc32c(data):
    c = 0xffffffff
    for b in data:
        c = _CRC[(c ^ b) & 255] ^ (c >> 8)
    return c ^ 0xffffffff


def reconstruct(plan, read_current, read_logical, checksum, sink, chunk=CHUNK):
    """Stream to a NEW candidate sink. Caller quarantines failed/partial output.

    checksum(address) returns a captured uint32 CRC32C, or None if absent.
    It must come from independently acquired checksum records, not be generated
    from the same old-block bytes for a real recovery claim.
    """
    require(plan['status'] == 'candidate_complete', 'incomplete_plan')
    require(1 <= chunk <= CHUNK, 'chunk_limit')
    metrics = {'old_block_reads':0,'anchor_bytes':0,'output_bytes':0,'max_request_bytes':0}

    @lru_cache(maxsize=256)
    def checked_block(address):
        require(address % BLOCK == 0, 'block_alignment')
        data = read_logical(address, BLOCK)
        require(len(data) == BLOCK, 'short_old_block')
        want = checksum(address)
        require(want is not None, 'missing_block_checksum')
        require(crc32c(data) == want, 'old_block_checksum_mismatch')
        metrics['old_block_reads'] += 1
        metrics['max_request_bytes'] = max(metrics['max_request_bytes'],BLOCK)
        return data

    def old_read(address, length):
        out = bytearray()
        while length:
            base = address // BLOCK * BLOCK
            skip = address-base
            take = min(length, BLOCK-skip)
            out.extend(checked_block(base)[skip:skip+take])
            address += take
            length -= take
        return bytes(out)

    used = {s['candidate_id'] for s in plan['spans'] if s['kind']=='old'}
    for c in plan['candidates']:
        if c['id'] not in used:
            continue
        for a,b in c['plain_checks']:
            while a < b:
                length = min(chunk,b-a)
                current = read_current(a,length)
                require(len(current)==length, 'short_current_read')
                require(old_read(c['logical']+a-c['file_base'],length)==current,'plaintext_anchor_mismatch')
                metrics['anchor_bytes'] += length
                a += length
    digest = hashlib.sha256()
    for s in plan['spans']:
        a,b = s['start'],s['end']
        while a < b:
            length = min(chunk,b-a)
            data = old_read(s['logical']+a-s['start'],length) if s['kind']=='old' else read_current(a,length)
            require(len(data)==length,'short_output_source')
            written = sink.write(data)
            require(written == len(data), 'short_output_write')
            digest.update(data)
            metrics['output_bytes'] += length
            metrics['max_request_bytes'] = max(metrics['max_request_bytes'],length)
            a += length
    require(metrics['output_bytes']==plan['size'],'output_size')
    return dict(metrics,sha256=digest.hexdigest(),classification='mapped_candidate_checks_passed_format_pending')
