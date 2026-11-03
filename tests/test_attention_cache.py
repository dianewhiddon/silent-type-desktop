import unittest
from types import SimpleNamespace

import torch

from silent_type import recognition


class SourceAttentionCacheTests(unittest.TestCase):
    def attention(self):
        from espnet.nets.pytorch_backend.transformer.attention import MultiHeadedAttention

        torch.manual_seed(0)
        return MultiHeadedAttention(4, 32, 0.0).eval()

    def test_cached_output_matches_the_original_for_every_step(self):
        plain = self.attention()
        cached = self.attention()
        searches = [1]
        recognition.cache_source_attention(
            SimpleNamespace(decoders=[SimpleNamespace(src_attn=cached)]), searches
        )
        memory = torch.randn(1, 12, 32)
        mask = torch.ones(1, 1, 12, dtype=torch.bool)
        with torch.inference_mode():
            for hypotheses in (1, 3, 4, 2):
                query = torch.randn(hypotheses, 5, 32)
                expanded = memory.expand(hypotheses, -1, -1)
                want = plain(query, expanded, expanded, mask.expand(hypotheses, -1, -1))
                got = cached(query, expanded, expanded, mask.expand(hypotheses, -1, -1))
                torch.testing.assert_close(got, want)

    def test_a_new_phrase_drops_the_cache(self):
        plain = self.attention()
        cached = self.attention()
        searches = [1]
        recognition.cache_source_attention(
            SimpleNamespace(decoders=[SimpleNamespace(src_attn=cached)]), searches
        )
        query = torch.randn(2, 3, 32)
        mask = torch.ones(2, 1, 12, dtype=torch.bool)
        with torch.inference_mode():
            for search in (1, 2):
                searches[0] = search
                memory = torch.randn(1, 12, 32).expand(2, -1, -1)
                torch.testing.assert_close(
                    cached(query, memory, memory, mask), plain(query, memory, memory, mask)
                )

    def test_different_key_and_value_use_the_original_path(self):
        plain = self.attention()
        cached = self.attention()
        recognition.cache_source_attention(SimpleNamespace(decoders=[SimpleNamespace(src_attn=cached)]), [1])
        query, key, value = torch.randn(2, 3, 32), torch.randn(2, 12, 32), torch.randn(2, 12, 32)
        mask = torch.ones(2, 1, 12, dtype=torch.bool)
        with torch.inference_mode():
            torch.testing.assert_close(cached(query, key, value, mask), plain(query, key, value, mask))


if __name__ == "__main__":
    unittest.main()
