import json
import os
import urllib.request
import urllib.error
from typing import Dict, List, Callable, Optional


class CodeGenerator:
    def __init__(self):
        pass

    def generate_agent_functions(
        self,
        function_file_path: str,
        provider: str,
        model: str,
        api_key: str = '',
        endpoint: str = '',
        temperature: float = 0.2,
        max_tokens: int = 4096,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict:
        try:
            if not os.path.exists(function_file_path):
                return {
                    'success': False,
                    'message': f'Function file not found: {function_file_path}'
                }

            functions = []
            with open(function_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            func_data = json.loads(line)
                            functions.append(func_data)
                        except json.JSONDecodeError:
                            continue

            human_functions = [func for func in functions if func.get('agent', '') == 'human']
            if not human_functions:
                return {
                    'success': False,
                    'message': 'No human functions found to generate from'
                }

            max_id = max((func.get('id', 0) for func in functions), default=0)

            if not endpoint:
                endpoint = self._get_default_endpoint(provider)
            if not model:
                model = self._get_default_model(provider)

            generated_count = 0
            total_count = len(human_functions)

            with open(function_file_path, 'a', encoding='utf-8') as f:
                for i, human_func in enumerate(human_functions):
                    try:
                        code = human_func.get('code', '')
                        language = human_func.get('language', '')
                        ext = human_func.get('ext', '')

                        if not code:
                            continue

                        use_mode2 = (i % 2 == 1)

                        if use_mode2:
                            generated_code = self._generate_via_nl(
                                provider=provider,
                                model=model,
                                api_key=api_key,
                                endpoint=endpoint,
                                source_code=code,
                                source_lang=language,
                                temperature=temperature,
                                max_tokens=max_tokens
                            )
                            agent_label = f"{model}_nl2code"
                        else:
                            generated_code = self._call_llm(
                                provider=provider,
                                model=model,
                                api_key=api_key,
                                endpoint=endpoint,
                                source_code=code,
                                source_lang=language,
                                temperature=temperature,
                                max_tokens=max_tokens
                            )
                            agent_label = f"{model}_code2code"

                        if not generated_code:
                            continue

                        max_id += 1
                        new_func = {
                            'id': max_id,
                            'pr_id': human_func.get('pr_id', 0),
                            'commit_id': human_func.get('commit_id', 0),
                            'diff_id': human_func.get('diff_id', 0),
                            'ext': ext,
                            'language': language,
                            'file_id': human_func.get('file_id', 0),
                            'code': generated_code,
                            'start_line': human_func.get('start_line', 0),
                            'end_line': human_func.get('end_line', 0),
                            'agent': agent_label
                        }
                        f.write(json.dumps(new_func, ensure_ascii=False) + '\n')
                        generated_count += 1

                    except Exception as e:
                        print(f"Failed to generate for function {human_func.get('id')}: {e}")
                        continue

                    if progress_callback:
                        progress_callback(generated_count, total_count)

            agent_stats = {}
            with open(function_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            func_data = json.loads(line)
                            agent = func_data.get('agent', 'unknown')
                            if agent not in agent_stats:
                                agent_stats[agent] = 0
                            agent_stats[agent] += 1
                        except json.JSONDecodeError:
                            continue

            return {
                'success': True,
                'message': f'Successfully generated {generated_count} agent functions',
                'generated_count': generated_count,
                'total_count': total_count,
                'agent_stats': agent_stats,
                'output_file': function_file_path
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'Failed to generate agent code: {str(e)}'
            }

    def _generate_via_nl(
        self,
        provider: str,
        model: str,
        api_key: str,
        endpoint: str,
        source_code: str,
        source_lang: str,
        temperature: float,
        max_tokens: int
    ) -> str:
        nl_description = self._call_llm_code_to_nl(
            provider=provider,
            model=model,
            api_key=api_key,
            endpoint=endpoint,
            source_code=source_code,
            source_lang=source_lang,
            temperature=temperature,
            max_tokens=max_tokens
        )

        if not nl_description:
            return ''

        generated_code = self._call_llm_nl_to_code(
            provider=provider,
            model=model,
            api_key=api_key,
            endpoint=endpoint,
            nl_description=nl_description,
            target_lang=source_lang,
            temperature=temperature,
            max_tokens=max_tokens
        )

        return generated_code

    def _call_llm_code_to_nl(
        self,
        provider: str,
        model: str,
        api_key: str,
        endpoint: str,
        source_code: str,
        source_lang: str,
        temperature: float,
        max_tokens: int
    ) -> str:
        system_prompt = (
            "You are a senior software engineer. "
            "Read the source code and produce a detailed natural language description of its behavior, "
            "inputs, outputs, logic flow, and key constraints. Do not include code in your response."
        )

        user_prompt = f"""Describe the following {source_lang} code in natural language.

Include:
1. What the function does (purpose and behavior)
2. Input parameters and their meanings
3. Return value and its meaning
4. Key logic steps and decision points
5. Important constraints or edge cases

Source code:
```{source_lang}
{source_code}
```"""

        return self._send_llm_request(
            provider=provider,
            model=model,
            api_key=api_key,
            endpoint=endpoint,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            extract_code=False
        )

    def _call_llm_nl_to_code(
        self,
        provider: str,
        model: str,
        api_key: str,
        endpoint: str,
        nl_description: str,
        target_lang: str,
        temperature: float,
        max_tokens: int
    ) -> str:
        system_prompt = (
            "You are a senior software engineer. "
            "Given a natural language description of a function, produce a fresh implementation in the specified language. "
            "Preserve functionality, inputs, outputs, and constraints, but freely choose naming, structure, "
            "control flow, and local organization. Return code only."
        )

        user_prompt = f"""Create a fresh implementation in {target_lang} based on this description.

Hard requirements:
1. Preserve all functionality, inputs, outputs, and constraints described.
2. Produce a fresh implementation with your own naming and structure.
3. Do not explain the code.
4. Output raw code only. Do not include markdown fences.

Description:
{nl_description}"""

        return self._send_llm_request(
            provider=provider,
            model=model,
            api_key=api_key,
            endpoint=endpoint,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            extract_code=True
        )

    def _call_llm(
        self,
        provider: str,
        model: str,
        api_key: str,
        endpoint: str,
        source_code: str,
        source_lang: str,
        temperature: float,
        max_tokens: int
    ) -> str:
        system_prompt = (
            "You are a senior software engineer. "
            "Read the source code, understand its behavior, and produce a fresh implementation in the same language. "
            "Preserve functionality, main interfaces, and important constraints, but freely change naming, structure, "
            "control flow, helper decomposition, and local organization. Return code only."
        )

        user_prompt = f"""Create a fresh implementation of the following {source_lang} code in the same language.

Hard requirements:
1. Preserve functionality, inputs, outputs, and major interfaces.
2. Treat the source as behavior reference, not as text to lightly edit.
3. Produce a fresh implementation with noticeably different structure and expression.
4. Avoid copying long spans from the original code.
5. Do not explain the code.
6. Output raw code only. Do not include markdown fences.

Source code:
```{source_lang}
{source_code}
```"""

        return self._send_llm_request(
            provider=provider,
            model=model,
            api_key=api_key,
            endpoint=endpoint,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            extract_code=True
        )

    def _send_llm_request(
        self,
        provider: str,
        model: str,
        api_key: str,
        endpoint: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        extract_code: bool
    ) -> str:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "stream": False
        }
        if max_tokens > 0:
            payload["max_tokens"] = max_tokens

        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            endpoint,
            data=data,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            method="POST"
        )

        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                raw_response = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM request failed, HTTP {exc.code}: {error_body}")
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Failed to connect to model service: {exc}")

        choices = raw_response.get("choices") or []
        if not choices:
            raise RuntimeError(f"Model response missing choices: {raw_response}")

        message = choices[0].get("message") or {}
        content = message.get("content", "")
        if not content:
            raise RuntimeError(f"Model response content is empty: {raw_response}")

        if extract_code:
            return self._extract_code_block(content)
        return content.strip()

    def _extract_code_block(self, text: str) -> str:
        import re
        pattern = re.compile(r"```(?:[\w.+-]+)?\s*\n(.*?)```", re.DOTALL)
        match = pattern.search(text)
        if match:
            return match.group(1).strip() + "\n"

        lines = text.splitlines()
        if lines and re.match(r"^\s*```[\w.+-]*\s*$", lines[0]):
            lines = lines[1:]
        if lines and re.match(r"^\s*```\s*$", lines[-1]):
            lines = lines[:-1]
        return "\n".join(lines).strip() + "\n"

    def _get_default_endpoint(self, provider: str) -> str:
        endpoints = {
            'zhipu': 'https://open.bigmodel.cn/api/paas/v4/chat/completions',
            'dashscope': 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions',
            'deepseek': 'https://api.deepseek.com/chat/completions',
        }
        return endpoints.get(provider.lower(), '')

    def _get_default_model(self, provider: str) -> str:
        models = {
            'zhipu': 'glm-4.7-flash',
            'dashscope': 'qwen3.5-flash',
            'deepseek': 'deepseek-v4-flash',
        }
        return models.get(provider.lower(), '')